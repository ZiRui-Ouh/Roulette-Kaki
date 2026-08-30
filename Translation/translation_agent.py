# Use the Conversation API to send a text message to Amazon Nova.

import boto3
from botocore.exceptions import ClientError

# Create a Bedrock Runtime client in the AWS Region you want to use.
client = boto3.client("bedrock-runtime", region_name="us-east-1")

# Set the model ID, e.g., Amazon Nova Lite.
model_id = "us.amazon.nova-2-lite-v1:0"

# Select language
to_translate = input("Please input the text you want to translate: ")
languages = {"Chinese", "Malay", "Tamil"}

def select_by_name(options_set):
    while True:
        print(f"\nAvailable options: {', '.join(options_set)}")
        choice = input("Type your choice: ").strip()
        
        if choice in options_set:
            return choice
            
        print("That item is not in the set. Please try again.")

target_language = select_by_name(languages)
prompt = f"You are a helpful translator. Translate the sentence after ':' directly into {target_language} without any extra conversational filler: {to_translate}"

print(prompt)
# Start a conversation with the user message.
conversation = [
    {
        "role": "user",
        "content": [{"text": prompt}],
    }
]
try:
    # Send the message to the model, using a basic inference configuration.
    response = client.converse(
        modelId=model_id,
        messages=conversation,
        inferenceConfig={"maxTokens": 512, "temperature": 0.5, "topP": 0.9},
    )

    # Extract and print the response text.
    response_text = response["output"]["message"]["content"][0]["text"]
    print(response_text)

except (ClientError, Exception) as e:
    print(f"ERROR: Can't invoke '{model_id}'. Reason: {e}")
    exit(1)


