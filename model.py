import json
import re
import numpy as np
import nltk
from nltk.corpus import stopwords
from keras.models import load_model
from sentence_transformers import SentenceTransformer
import torch

class DepartmentClassifier:
    def __init__(self, model_path, embedding_model_name, labels_path):
        """Initialize the department classifier."""
        # Load the trained model
        self.model = load_model(model_path)
        
        # Load the embedding model
        self.embedding_model = SentenceTransformer(embedding_model_name)
        
        # Load labels
        with open(labels_path, 'r') as f:
            self.labels = json.load(f)
        self.inverse_labels = {v: k for k, v in self.labels.items()}

        # Ensure NLTK stopwords are downloaded
        nltk.download('stopwords', quiet=True)
        self.stop_words = set(stopwords.words('english'))

    def preprocess_text(self, text):
        """Preprocess the input text."""
        if not isinstance(text, str):
            text = str(text)
        text = text.lower()
        text = re.sub(r'[^a-zA-Z\s]', '', text)
        text = ' '.join(word for word in text.split() if word not in self.stop_words)
        return text

    def predict_department(self, query):
        """Predict the department based on the input query."""
        try:
            # Preprocess the query
            query = self.preprocess_text(query)
            
            # Generate embedding
            query_embedding = self.embedding_model.encode(query)
            if isinstance(query_embedding, torch.Tensor):
                query_embedding = query_embedding.cpu().numpy()
            
            # Ensure correct shape
            if len(query_embedding.shape) == 1:
                query_embedding = query_embedding.reshape(1, -1)
            
            # Predict department
            prediction = self.model.predict(query_embedding)
            predicted_label = np.argmax(prediction)
            
            # Map label back to department
            return self.inverse_labels[predicted_label]
            
        except Exception as e:
            print(f"Error during prediction: {str(e)}")
            return "Unknown"