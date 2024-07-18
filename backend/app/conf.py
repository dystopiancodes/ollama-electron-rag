import json
import os

class Config:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.default_config = {
            "prompt_template": """Sei un assistente AI che risponde in italiano. Utilizza le seguenti informazioni di contesto per rispondere alla domanda. 
Rispondi in modo conciso e diretto, senza spiegare il tuo ragionamento. Usa solo la lingua italiana.
Se non conosci la risposta, rispondi semplicemente "Non ho informazioni sufficienti per rispondere a questa domanda."

Contesto:
{context}

Domanda: {question}

Risposta concisa in italiano:"""
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