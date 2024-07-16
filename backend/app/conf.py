import json
import os

class Config:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.default_config = {
            "prompt_template": """You are a helpful AI assistant. Use the following pieces of context to answer the question at the end. 
            If you don't know the answer, just say that you don't know, don't try to make up an answer.

            Context: {context}

            Human: {question}

            Assistant: """
        }
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return self.default_config.copy()

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get_prompt_template(self):
        return self.config.get('prompt_template', self.default_config['prompt_template'])

    def set_prompt_template(self, new_template):
        self.config['prompt_template'] = new_template
        self.save_config()

    def reset_to_default(self):
        self.config = self.default_config.copy()
        self.save_config()

config = Config()