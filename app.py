import os
from flask import Flask, request, jsonify, render_template
from elasticsearch import Elasticsearch
import openai

# Load Env File
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Load Envs
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELASTICSEARCH_ENDPOINT = os.getenv("ELASTICSEARCH_ENDPOINT")
ELASTICSEARCH_API_KEY = os.getenv("ELASTICSEARCH_API_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")
OPENAI_MODEL= os.getenv("OPENAI_MODEL")

openai.api_key = OPENAI_API_KEY

# Connect to Elasticsearch
es = Elasticsearch(ELASTICSEARCH_ENDPOINT, api_key=ELASTICSEARCH_API_KEY)


def generate_dsl_query(question):
    """
    Uses OpenAI API to convert a natural language question into an Elasticsearch Query DSL.
    """
    prompt = f"""
    Instructions:
    - Your name now is Elastic Sales Assistant and your job is to answer questions about sales
    - The field that contains the price paid is Total Amount
    - The field that contains the date of purchase is Date
    - The field Gender contains information about customer's gender and you should consider either Male or Female
    - The questions will be made in English and, when not, will be made in Portuguese. Please translate to English
    - Convert the following question into an Elasticsearch Query DSL, using this mapping properties:

    "properties": {{

        "@timestamp": {{"type": "date"}},
        "Age": {{"type": "long"}},
        "Customer ID": {{"type": "keyword"}},
        "Date":{{"type": "date","format": "iso8601"}},
        "Gender": {{"type": "keyword"}},
        "Price per Unit": {{"type": "long"}},
        "Product Category": {{"type": "keyword"}},
        "Quantity": {{ "type": "long"}},
        "Total Amount": {{"type": "long"}}
        }}

    Question: "{question}"

    - Respond with only valid JSON query without any additional explanations or syntax formatter like mardown.
    """
    try:
        response = openai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": "You are an Elasticsearch Query DSL expert."},
                    {"role": "user", "content": prompt}]
        )
    
    except OpenAIError as e:
        print(f"Error: {e}")
        return "Failed to generate response from OpenAI"

    # Parse the response and return the generated query
    dsl_query = response.choices[0].message.content
    return dsl_query.strip()
    
def execute_query(index, query_dsl):
    """
    Executes the DSL query in Elasticsearch.
    """
    try:
        query = eval(query_dsl)  # Convert string JSON to Python dictionary
        response = es.search(index=index, body=query)
        return response
    except Exception as e:
        return {"error": str(e)}

def format_response(question, es_response):
    """
    Converts the Elasticsearch response into a natural language answer.
    """
    
    prompt = f"""
    Instructions:
    - Your name now is Elastic Sales Assistant
    - Convert the following document in a natural language to answer the question:

    Question: "{question}"
    Response: "{es_response}"

    - Respond like you are talking with a human.
    """
    try:
        response = openai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": "You are an Elasticsearch Query DSL expert."},
                    {"role": "user", "content": prompt}]
        )
    except OpenAIError as e:
        return "Could not process the response."

    # Parse the response and return the generated query
    dsl_query = response.choices[0].message.content
    return dsl_query.strip()

# Route to serve the index.html file
@app.route("/")
def index():
    return render_template("index.html")

# Flask route for the API endpoint
@app.route("/ask", methods=["POST"])
def ask_question():
    data = request.json
    question = data.get("question", "")
    index = INDEX_NAME
    
    if not question:
        return jsonify({"error": "No question provided"}), 400

    # Get Elasticsearch results
    dsl_query = generate_dsl_query(question)
    es_response = execute_query(index, dsl_query)
    answer = format_response(question, es_response)
    print (dsl_query)
    return jsonify({"answer": answer})

if __name__ == "__main__":
    app.run(debug=True)
