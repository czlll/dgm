
import argparse
import subprocess
import logging
from logging.handlers import RotatingFileHandler
import os
import threading

from llm_withtools import CLAUDE_MODEL, OPENAI_MODEL, chat_with_agent
from utils.eval_utils import get_report_score, msg_history_to_report, score_tie_breaker
from utils.git_utils import diff_versus_commit, reset_to_commit, apply_patch, is_patch_empty_or_test_only, get_patch_summary

# Thread-local storage for logger instances
thread_local = threading.local()
code_agent_model = 'o3-mini'

def get_thread_logger():
    """
    Get the logger instance specific to the current thread.
    Returns None if no logger has been set for this thread.
    """
    return getattr(thread_local, 'logger', None)

def set_thread_logger(logger):
    """
    Set the logger instance for the current thread.
    """
    thread_local.logger = logger

def setup_logger(log_file='./chat_history.md', level=logging.INFO):
    """
    Set up a logger with both file and console handlers.
    """
    # Create logger with a unique name based on thread ID
    logger = logging.getLogger(f'AgenticSystem-{threading.get_ident()}')
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers = []
    
    # Create formatters
    file_formatter = logging.Formatter('%(message)s')
    
    # Create and set up file handler
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
    file_handler.setLevel(level)
    file_handler.setFormatter(file_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    
    # Store logger in thread-local storage
    set_thread_logger(logger)
    
    return logger

def safe_log(message, level=logging.INFO):
    """
    Thread-safe logging function that ensures messages go to the correct logger.
    """
    logger = get_thread_logger()
    if logger:
        logger.log(level, message)
    else:
        print(f"Warning: No logger found for thread {threading.get_ident()}")

class AgenticSystem:
    def __init__(
            self,
            problem_statement,
            git_tempdir,
            base_commit,
            chat_history_file='./chat_history.md',
            test_description=None,
            self_improve=False,
            instance_id=None,
            max_attempts=3,
            max_patch_retries=2,
            model=None,
        ):
        self.problem_statement = problem_statement
        self.git_tempdir = git_tempdir
        self.base_commit = base_commit
        self.chat_history_file = chat_history_file
        self.test_description = test_description
        self.self_improve = self_improve
        self.instance_id = instance_id if not self_improve else 'dgm'
        self.code_model = code_agent_model if code_agent_model else CLAUDE_MODEL
        self.max_attempts = max_attempts
        self.max_patch_retries = max_patch_retries

        # Initialize logger and store it in thread-local storage
        self.logger = setup_logger(chat_history_file)
        
        # Clear the log file
        with open(chat_history_file, 'w') as f:
            f.write('')
        
        # Track attempts and results
        self.attempt_history = []
        self.best_score = -1
        self.best_patch = None
        self.best_test_report = None

    def get_current_edits(self):
        diff = str(diff_versus_commit(self.git_tempdir, self.base_commit))
        return diff

    def get_regression_tests(self):
        """
        Get the regression tests from the repository.
        """
        instruction = f"""I have uploaded a Python code repository in the directory {self.git_tempdir}.

<problem_description>
{self.problem_statement}
</problem_description>

<test_description>
{self.test_description}
</test_description>

Your task is to identify regression tests in the {self.git_tempdir} directory that should pass both before and after addressing the <problem_description>. I have already taken care of the required dependencies.
At the end, please provide a summary that includes where the regression tests are located, what they are testing, and how they can be executed.
"""

        new_msg_history = chat_with_agent(instruction, model=self.code_model, msg_history=[], logging=safe_log)
        regression_tests_summary = new_msg_history[-1]
        try:
            regression_tests_summary = regression_tests_summary['content'][-1]['text']
        except:
            pass
        return regression_tests_summary

    def run_regression_tests(self, regression_tests_summary):
        """
        Run the regression tests and get the test report.
        """
        code_diff = self.get_current_edits()
        instruction = f"""I have uploaded a Python code repository in the directory {self.git_tempdir}. There is an attempt to address the problem statement. Please review the changes and run the regression tests.

<problem_description>
{self.problem_statement}
</problem_description>

<attempted_solution>
{code_diff}
</attempted_solution>

<test_description>
{self.test_description}
</test_description>

<regression_tests_summary>
{regression_tests_summary}
</regression_tests_summary>

Your task is to run the regression tests in the {self.git_tempdir} directory to ensure that the changes made to the code address the <problem_description>.
"""
        new_msg_history = chat_with_agent(instruction, model=self.code_model, msg_history=[], logging=safe_log)
        test_report = msg_history_to_report(self.instance_id, new_msg_history, model=self.code_model)
        return test_report

    def validate_patch(self, patch_str):
        """
        Validate if a patch modifies source files (non-test files).
        
        Returns:
            tuple: (is_valid, summary, modified_files)
        """
        is_empty, is_test_only, modified_files = is_patch_empty_or_test_only(patch_str)
        summary = get_patch_summary(patch_str)
        
        is_valid = not is_empty and not is_test_only
        
        return is_valid, summary, modified_files

    def generate_solution_with_retry(self, instruction, attempt_num=1):
        """
        Generate a solution with retry logic for invalid patches.
        
        Returns:
            tuple: (msg_history, patch_str, is_valid)
        """
        retry_count = 0
        
        while retry_count <= self.max_patch_retries:
            safe_log(f"=== Attempt {attempt_num}, Patch Generation Retry {retry_count + 1} ===")
            
            # Add retry context to instruction if this is a retry
            current_instruction = instruction
            if retry_count > 0:
                current_instruction = f"""{instruction}

IMPORTANT: Your previous attempt generated a patch that was either empty or only modified test files. 
This does not solve the underlying problem. Please ensure your solution:

1. Modifies actual source code files (not just test files)
2. Addresses the core issue described in the problem statement
3. Makes meaningful changes to the codebase

Previous patch summary: {self.last_patch_summary if hasattr(self, 'last_patch_summary') else 'No valid patch generated'}

Please generate a new solution that modifies source files to fix the problem."""
            
            # Generate solution
            new_msg_history = chat_with_agent(current_instruction, model=self.code_model, msg_history=[], logging=safe_log)
            
            # Get the current patch
            patch_str = self.get_current_edits()
            
            # Validate the patch
            is_valid, summary, modified_files = self.validate_patch(patch_str)
            
            safe_log(f"Patch validation result: {summary}")
            
            if is_valid:
                safe_log(f"✓ Valid patch generated on retry {retry_count + 1}")
                return new_msg_history, patch_str, True
            else:
                safe_log(f"✗ Invalid patch on retry {retry_count + 1}: {summary}")
                self.last_patch_summary = summary
                retry_count += 1
                
                # Reset to base commit for next retry
                if retry_count <= self.max_patch_retries:
                    reset_to_commit(self.git_tempdir, self.base_commit)
        
        safe_log(f"✗ Failed to generate valid patch after {self.max_patch_retries + 1} attempts")
        return new_msg_history, patch_str, False

    def build_attempt_context(self, attempt_num):
        """
        Build context from previous attempts to include in the prompt.
        """
        if not self.attempt_history:
            return ""
        
        context_parts = ["\n=== PREVIOUS ATTEMPTS CONTEXT ==="]
        context_parts.append(f"You have made {len(self.attempt_history)} previous attempt(s). Learn from them to improve your solution.")
        
        if self.best_score >= 0:
            context_parts.append(f"Current best test score: {self.best_score:.2%}")
        
        for i, attempt in enumerate(self.attempt_history[-2:], 1):  # Show last 2 attempts
            context_parts.append(f"\n--- Previous Attempt {len(self.attempt_history) - 2 + i} ---")
            context_parts.append(f"Test Score: {attempt['score']:.2%}")
            context_parts.append(f"Patch Summary: {attempt['patch_summary']}")
            
            # Include a snippet of the patch for context
            patch_lines = attempt['patch'].split('\n')
            if len(patch_lines) > 20:
                patch_snippet = '\n'.join(patch_lines[:10] + ['...', '(patch truncated)'] + patch_lines[-10:])
            else:
                patch_snippet = attempt['patch']
            
            context_parts.append(f"Patch Content:\n```diff\n{patch_snippet}\n```")
            
            if attempt['test_report']:
                failed_tests = [test for test, result in attempt['test_report'].items() if result != 'PASSED']
                if failed_tests:
                    context_parts.append(f"Failed Tests: {', '.join(failed_tests[:5])}")  # Show first 5 failed tests
        
        context_parts.append("\nPlease analyze the previous attempts and generate an improved solution.")
        context_parts.append("Focus on addressing any failing tests and improving the overall approach.")
        context_parts.append("=== END PREVIOUS ATTEMPTS CONTEXT ===\n")
        
        return '\n'.join(context_parts)

    def forward(self):
        """
        The enhanced forward function with multi-attempt logic and patch validation.
        """
        safe_log(f"=== Starting AgenticSystem with {self.max_attempts} attempts ===")
        
        # Get regression tests once at the beginning
        regression_tests_summary = None
        if self.test_description:
            safe_log("=== Getting Regression Tests ===")
            regression_tests_summary = self.get_regression_tests()
        
        candidates = []
        
        for attempt_num in range(1, self.max_attempts + 1):
            safe_log(f"\n=== ATTEMPT {attempt_num}/{self.max_attempts} ===")
            
            # Reset to base commit for each attempt
            reset_to_commit(self.git_tempdir, self.base_commit)
            
            # Build instruction with context from previous attempts
            base_instruction = f"""I have uploaded a Python code repository in the directory {self.git_tempdir}. Help solve the following problem.

<problem_description>
{self.problem_statement}
</problem_description>

<test_description>
{self.test_description}
</test_description>

Your task is to make changes to the files in the {self.git_tempdir} directory to address the <problem_description>. I have already taken care of the required dependencies.
"""
            
            # Add context from previous attempts
            attempt_context = self.build_attempt_context(attempt_num)
            instruction = base_instruction + attempt_context
            
            # Generate solution with retry logic for invalid patches
            msg_history, patch_str, is_valid = self.generate_solution_with_retry(instruction, attempt_num)
            
            if not is_valid:
                safe_log(f"✗ Attempt {attempt_num} failed to generate valid patch")
                continue
            
            # Run regression tests if available
            test_report = {}
            score = 0.0
            
            if regression_tests_summary:
                safe_log(f"=== Running Tests for Attempt {attempt_num} ===")
                test_report = self.run_regression_tests(regression_tests_summary)
                score = get_report_score(test_report)
                safe_log(f"Test score for attempt {attempt_num}: {score:.2%}")
            
            # Store attempt results
            patch_summary = get_patch_summary(patch_str)
            attempt_result = {
                'attempt_num': attempt_num,
                'patch': patch_str,
                'patch_summary': patch_summary,
                'test_report': test_report,
                'score': score,
                'msg_history': msg_history
            }
            
            self.attempt_history.append(attempt_result)
            candidates.append(attempt_result)
            
            # Update best score and patch
            if score > self.best_score:
                self.best_score = score
                self.best_patch = patch_str
                self.best_test_report = test_report
                safe_log(f"✓ New best score: {score:.2%}")
            
            safe_log(f"Attempt {attempt_num} completed - Score: {score:.2%}, Patch: {patch_summary}")
        
        # Select the best candidate
        if not candidates:
            safe_log("✗ No valid patches generated across all attempts")
            return
        
        # Find candidates with the best score
        best_score = max(candidate['score'] for candidate in candidates)
        best_candidates = [c for c in candidates if c['score'] == best_score]
        
        safe_log(f"\n=== SELECTING BEST SOLUTION ===")
        safe_log(f"Found {len(best_candidates)} candidate(s) with best score: {best_score:.2%}")
        
        if len(best_candidates) == 1:
            best_candidate = best_candidates[0]
            safe_log(f"✓ Single best candidate: Attempt {best_candidate['attempt_num']}")
        else:
            # Use tie-breaker for multiple candidates with same score
            safe_log(f"Using tie-breaker to select among {len(best_candidates)} candidates")
            
            code_diffs = [c['patch'] for c in best_candidates]
            test_reports = [c['test_report'] for c in best_candidates]
            best_indices = list(range(len(best_candidates)))
            
            try:
                best_index = score_tie_breaker(
                    self.problem_statement, 
                    code_diffs, 
                    test_reports, 
                    best_indices, 
                    logging=safe_log
                )
                best_candidate = best_candidates[best_index]
                safe_log(f"✓ Tie-breaker selected: Attempt {best_candidate['attempt_num']}")
            except Exception as e:
                safe_log(f"Tie-breaker failed: {e}, using first candidate")
                best_candidate = best_candidates[0]
        
        # Apply the best patch
        safe_log(f"\n=== APPLYING FINAL SOLUTION ===")
        reset_to_commit(self.git_tempdir, self.base_commit)
        apply_patch(self.git_tempdir, best_candidate['patch'])
        
        final_patch = self.get_current_edits()
        final_summary = get_patch_summary(final_patch)
        
        safe_log(f"✓ Final solution applied: {final_summary}")
        safe_log(f"✓ Final test score: {best_candidate['score']:.2%}")
        
        # Store final results
        self.best_patch = final_patch
        self.best_score = best_candidate['score']
        self.best_test_report = best_candidate['test_report']
        
        safe_log("=== AgenticSystem completed ===")
        
        return best_candidate['msg_history']

def main():
    parser = argparse.ArgumentParser(description='Process repository with an agentic system.')
    parser.add_argument('--problem_statement', required=True, help='The problem statement to process')
    parser.add_argument('--git_dir', required=True, help='Path to git repository directory')
    parser.add_argument('--base_commit', required=True, help='Base commit hash to compare against')
    parser.add_argument('--chat_history_file', required=True, help='Path to chat history file')
    parser.add_argument('--outdir', required=False, default="/dgm/", help='Output directory')
    parser.add_argument('--test_description', default=None, required=False, help='Description of how to test the repository')
    parser.add_argument('--self_improve', default=False, action='store_true', help='Whether to self-improve the repository or solving swe')
    parser.add_argument('--instance_id', default=None, help='Instance ID for SWE issue')
    parser.add_argument('--max_attempts', type=int, default=3, help='Maximum number of solution attempts')
    parser.add_argument('--max_patch_retries', type=int, default=2, help='Maximum number of patch generation retries per attempt')
    parser.add_argument('--model', default=None, help='Model to use (default: OpenAI o3-mini)')
    args = parser.parse_args()

    # Process the repository
    agentic_system = AgenticSystem(
        problem_statement=args.problem_statement,
        git_tempdir=args.git_dir,
        base_commit=args.base_commit,
        chat_history_file=args.chat_history_file,
        test_description=args.test_description,
        self_improve=args.self_improve,
        instance_id=args.instance_id,
        max_attempts=args.max_attempts,
        max_patch_retries=args.max_patch_retries,
        model=args.model,
    )

    # Run the agentic system to try to solve the problem
    agentic_system.forward()

    # Get code diff and save to model_patch.diff
    model_patch = diff_versus_commit(args.git_dir, args.base_commit)
    model_patch_outfile = os.path.join(args.outdir, 'model_patch.diff') if args.outdir else 'model_patch.diff'
    with open(model_patch_outfile, 'w') as f:
        f.write(model_patch)

if __name__ == "__main__":
    main()
