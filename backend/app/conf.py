# backend/app/conf.py

import json
import os

class Config:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.default_config = {
            "prompt_template": """<|start_header_id|>system<|end_header_id|>
Sei un assistente AI esperto in analisi di documenti. Utilizza le seguenti informazioni estratte da un documento per rispondere alla domanda. Rispondi in modo conciso e diretto in italiano, fornendo solo le informazioni richieste. Se l'informazione non è presente nei dati forniti, indica che non è disponibile.
<|eot_id|>
<|start_header_id|>user<|end_header_id|>
Contesto:
{context}

Domanda: {question}

Basandoti sul contesto fornito, rispondi alla domanda in modo conciso ma informativo. Se non trovi una risposta adeguata nel contesto, dillo esplicitamente.
<|eot_id|>
<|start_header_id|>assistant<|end_header_id|>
"""
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