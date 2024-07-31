# backend/app/utils.py


import os

def is_valid_document(filename):
    return (not filename.startswith('.') and 
            os.path.splitext(filename)[1].lower() in ['.pdf', '.xml'])