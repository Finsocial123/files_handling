# Document Chat API

A FastAPI application for processing and chatting with documents.

## Deploying on RunPod

### Option 1: Using the RunPod CLI

1. Install the RunPod CLI:
   ```bash
   pip install runpod
   ```

2. Login to RunPod:
   ```bash
   runpod login
   ```

3. Deploy the application:
   ```bash
   runpod deploy --name document-chat-api --github-url https://github.com/yourusername/your-repo.git
   ```

### Option 2: Using the RunPod Web Interface

1. Log in to your RunPod account at https://runpod.io/console/pods
2. Click "Deploy" to create a new pod
3. Select a template (usually GPU-enabled instances work best for LLM applications)
4. Under "Volume", select an existing storage volume or create a new one
5. Under "Advanced Options", set these environment variables:
   - `OPENAI_API_KEY` (if using OpenAI)
   - Any other environment variables from .env.example
6. In the "Dockerfile" section:
   - Select "GitHub" as the source
   - Enter your repository URL: `https://github.com/yourusername/your-repo.git`
   - Set the container port to 8000
7. Click "Deploy"

## Configuration

Create a `.env` file based on the `.env.example` template:

