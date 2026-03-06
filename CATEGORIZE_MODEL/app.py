from flask import Flask, request, render_template
import pickle
import nltk
from nltk.corpus import stopwords
from nltk.stem.porter import PorterStemmer

nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
import string

# Initialize PorterStemmer
ps = PorterStemmer()

def transform_text(text):
    text = text.lower()
    text = nltk.word_tokenize(text)
    y = []
    for i in text:
        if i.isalnum():
            y.append(i)
    text = y[:]
    y.clear()
    for i in text:
        if i not in stopwords.words('english') and i not in string.punctuation:
            y.append(i)
    text = y[:]
    y.clear()
    for i in text:
        y.append(ps.stem(i))
    return " ".join(y)

# Load vectorizer and model
with open('vectorizer.pkl', 'rb') as f:
    vectorizer = pickle.load(f)

with open('model.pkl', 'rb') as f:
    model = pickle.load(f)

# Category mapping
category_map = {
    "Important Notices": 4,
    "Work": 3,
    "Events": 2,
    "Personal": 1
}
# Reverse map for prediction
reverse_category_map = {v: k for k, v in category_map.items()}

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    if request.method == 'POST':
        text = request.form['text']
        transformed = transform_text(text)
        vectorized = vectorizer.transform([transformed])
        prediction = model.predict(vectorized)[0]
        prediction_label = reverse_category_map.get(prediction, "Unknown")
        return render_template('index.html', prediction=prediction_label)
    return render_template('index.html')


if __name__ == '__main__':
    app.run(port=8562,debug=True)
