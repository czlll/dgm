# AWS Credentials Setup for Bedrock Claude Models

If you want to use AWS Bedrock Claude models, you need to configure AWS credentials. Here are the steps:

## Option 1: Environment Variables

Set the following environment variables:

```bash
export AWS_ACCESS_KEY_ID=your_access_key_id
export AWS_SECRET_ACCESS_KEY=your_secret_access_key
export AWS_DEFAULT_REGION=us-east-1  # or your preferred region
```

## Option 2: AWS Credentials File

Create `~/.aws/credentials`:

```ini
[default]
aws_access_key_id = your_access_key_id
aws_secret_access_key = your_secret_access_key
```

And `~/.aws/config`:

```ini
[default]
region = us-east-1
```

## Option 3: Use OpenAI Instead (Recommended for Testing)

If you don't have AWS Bedrock access, use OpenAI models instead:

```bash
python coding_agent.py \
  --model "o3-mini-2025-01-31" \
  --problem_statement "Your problem" \
  --git_dir /path/to/repo \
  --base_commit abc123 \
  --chat_history_file history.md
```

## Option 4: Use Alternative Models

The system supports various models:

- OpenAI: `o3-mini-2025-01-31`, `gpt-4`, etc.
- Claude (Bedrock): `bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0`
- Other models as supported by the llm module

## Troubleshooting

If you see "could not resolve credentials from session":

1. Check that AWS credentials are properly configured
2. Verify the AWS region is correct
3. Ensure you have Bedrock access permissions
4. Try using OpenAI models instead for testing

## Default Behavior

The system now defaults to OpenAI models if no model is specified, avoiding AWS credential issues during testing and development.