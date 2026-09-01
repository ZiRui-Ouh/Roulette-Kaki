import boto3

class TranslationAgent:
    def __init__(self, target_language: str, source_language: str = "auto", region_name: str = "us-east-1"):
        """
        Initializes the Translation Agent.
        """
        self.target_language = target_language
        self.source_language = source_language
        self.model_id = "us.amazon.nova-2-lite-v1:0" 
        
        # Initialize the AWS Bedrock runtime client
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=region_name)
        
        # 1. Define strict system instructions to enforce exact output constraints
        self.system_prompts = [{
            "text": (
                f"You are an expert, highly accurate translation agent. "
                f"Translate the user's text from {self.source_language} to {self.target_language}. "
                f"CRITICAL RULE: Output ONLY the final translated string. Do not include quotes, ntroductory text, conversational filler, or explanations."
            )
        }]

    def translate(self, text: str) -> str:
        """
        Core agent function: Accepts strictly a string input, returns strictly a string output.
        """
        if not isinstance(text, str):
            raise ValueError("Input must be a string.")
            
        # 2. Format the user's input into the Converse API message structure
        messages = [{
            "role": "user",
            "content": [{"text": text}]
        }]
        
        try:
            # 3. Call the Bedrock Converse API
            response = self.bedrock_client.converse(
                modelId=self.model_id,
                system=self.system_prompts,
                messages=messages,
                inferenceConfig={"maxTokens": 512, "temperature": 0.1, "topP": 0.9} # Keep temperature low for accurate translation
            )
            
            # 4. Extract and return purely the translated string
            return response["output"]["message"]["content"][0]["text"].strip()
            
        except Exception as e:
            raise RuntimeError(f"Translation failed: {str(e)}")

# ==========================================
# Defining different language translation agents
# ==========================================

def Chinese_translate(input_string):
    Chinese_agent = TranslationAgent(target_language="Chinese")
    return Chinese_agent.translate(input_string)

    

    

def Malay_translate(input_string):
    Malay_agent = TranslationAgent(target_language="Malay")    
    return Malay_agent.translate(input_string)


    

def Tamil_translate(input_string):
    Tamil_agent = TranslationAgent(target_language="Tamil")
    return Tamil_agent.translate(input_string)

    


