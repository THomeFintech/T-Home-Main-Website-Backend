import joblib
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODEL_PATH = os.path.join(BASE_DIR, "models")

loan_model = joblib.load(os.path.join(MODEL_PATH, "loan_classifier.pkl"))
le_emp = joblib.load(os.path.join(MODEL_PATH, "encoder_employment.pkl"))
le_type = joblib.load(os.path.join(MODEL_PATH, "encoder_loan_type.pkl"))
explainer = joblib.load(os.path.join(MODEL_PATH, "shap_explainer.pkl"))
feature_names = joblib.load(os.path.join(MODEL_PATH, "feature_names.pkl"))