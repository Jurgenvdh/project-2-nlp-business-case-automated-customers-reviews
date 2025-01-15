# File: sentiment_analysis_streamlit_app.py

import pandas as pd
import joblib
import openai
import streamlit as st
from typing import List

# -- Set your OpenAI API key. Ensure you have it in streamlit secrets, or replace this with your key directly. --
openai.api_key = st.secrets["openai_api_key"]

# Constants (used if local files are present; optional if you rely on file upload)
DATA_FILE = 'amazon_reviews_clustered_sentiment.csv'
MODEL_FILE = 'sentiment_model.pkl'
VECTORIZER_FILE = 'tfidf_vectorizer.pkl'

def load_data(file_path: str) -> pd.DataFrame:
    """Load the dataset from the specified file path."""
    return pd.read_csv(file_path)

def load_model(file_path: str):
    """Load the SVM model."""
    return joblib.load(file_path)

def load_vectorizer(model, file_path: str):
    """Retrieve the vectorizer from the model or a separate file."""
    if hasattr(model, 'vectorizer'):
        return model.vectorizer
    return joblib.load(file_path)

def process_reviews(df: pd.DataFrame, vectorizer, model) -> pd.DataFrame:
    """Vectorize reviews and predict sentiment."""
    X = vectorizer.transform(df['reviews.text'])
    df['sentiment'] = model.predict(X)
    df['sentiment_score'] = df['sentiment'].map({'positive': 2, 'neutral': 1, 'negative': 0})
    return df

def calculate_average_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate average sentiment scores grouped by cluster and product name.
    """
    product_scores = df.groupby(['cluster_name', 'name'])['sentiment_score'].mean().reset_index()
    return df.merge(product_scores, on=['cluster_name', 'name'], suffixes=('', '_avg'))

def generate_article(category_name: str, top_products: List[str], bottom_product: str, reviews: str) -> str:
    """
    Generate an article using OpenAI API via text completions.
    Using the 'text-davinci-003' model for classic text generation.
    """
    prompt = f"""
    Write a blog post titled 'Top Products in {category_name}'.
    Include the following:
    - Introduction to the category.
    - Top 3 products: {', '.join(top_products)}.
      - Key differences between them.
      - When a consumer should choose one over another.
    - Common complaints or issues for each of these top products.
    - The worst product in the category: {bottom_product}.
      - Reasons why consumers should avoid it.
    - Conclusion with a recommendation.
    
    Use a friendly and informative tone, similar to articles on The Verge or Wirecutter.
    Incorporate insights from the following reviews:
    {reviews}
    
    Keep the article concise and engaging.
    """
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=prompt,
        max_tokens=1000,
        temperature=0.8,
    )
    return response.choices[0].text.strip()

# -------------------- Streamlit App -------------------- #
st.title("Sentiment Analysis and Article Generator")

# File Uploader widgets
uploaded_data = st.file_uploader("Upload Dataset (CSV)", type=["csv"])
uploaded_model = st.file_uploader("Upload Model (Pickle File)", type=["pkl"])
uploaded_vectorizer = st.file_uploader("Upload Vectorizer (Pickle File)", type=["pkl"])

# Main button: Process Data & Generate Articles
if st.button("Process and Generate Articles"):
    if uploaded_data and uploaded_model and uploaded_vectorizer:
        try:
            # Load the uploaded files
            df = load_data(uploaded_data)
            svm_model = load_model(uploaded_model)
            vectorizer = load_vectorizer(svm_model, uploaded_vectorizer)

            # Process reviews and calculate scores
            df = process_reviews(df, vectorizer, svm_model)
            df = calculate_average_scores(df)

            # Generate articles for each category (cluster_name)
            for category in df['cluster_name'].unique():
                st.subheader(f"Category: {category}")
                category_df = df[df['cluster_name'] == category]

                # Identify top 3 and bottom 1 products by average sentiment
                product_sentiments = (
                    category_df.groupby('name')['sentiment_score_avg']
                    .mean().reset_index()
                )
                top_products = product_sentiments.nlargest(3, 'sentiment_score_avg')['name'].tolist()
                bottom_product = product_sentiments.nsmallest(1, 'sentiment_score_avg')['name'].iloc[0]

                # Get a few sample reviews for the top products
                top_reviews = category_df[category_df['name'].isin(top_products)]['reviews.text'].tolist()

                # Generate the article
                article = generate_article(
                    category,
                    top_products,
                    bottom_product,
                    ' '.join(top_reviews[:5])  # Just take the first 5 reviews
                )

                # Display the article
                st.write(article)
                st.markdown("---")

        except Exception as e:
            st.error(f"Error: {str(e)}")
    else:
        st.warning("Please upload all required files.")
