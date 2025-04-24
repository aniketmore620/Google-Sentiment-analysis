# Enhanced Flask App with Login, Feedback (Database), and Professional UI

from flask import Flask, render_template, request, send_file, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
from googleapiclient.discovery import build
from textblob import TextBlob
import plotly.express as px
import plotly.io as pio
from collections import defaultdict, Counter
import io
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Change in production

# Google Custom Search API
API_KEY = 'AIzaSyD31p0SaRzsgDukTXeNfh2-VUFgFkr0dMM'
CSE_ID = '05cbd35a1cb374715'

# Configure SQLite DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///feedback.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Feedback Model
class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    message = db.Column(db.Text)

# Dummy credentials for login
USERS = {'admin': 'password123'}

# Google Search Wrapper
def google_search(search_term, api_key, cse_id, **kwargs):
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=search_term, cx=cse_id, **kwargs).execute()
    return res

# Helper to render DataFrame as HTML
def render_table_html(df):
    return df.to_html(classes='data table table-bordered', index=False, escape=False)

# Keyword frequency in results
def get_keyword_frequency(results, keywords):
    keyword_freq = defaultdict(lambda: {'title': 0, 'snippet': 0})
    for item in results:
        title = item.get('title', '').lower()
        snippet = item.get('snippet', '').lower()
        for keyword in keywords:
            if keyword in title:
                keyword_freq[keyword]['title'] += 1
            if keyword in snippet:
                keyword_freq[keyword]['snippet'] += 1
    return keyword_freq

# Plot: Sentiment Analysis

def plot_sentiment_analysis(sentiments):
    df = pd.DataFrame({'sentiment': sentiments})
    fig = px.histogram(df, x='sentiment', title='Sentiment Analysis', color='sentiment',
                       color_discrete_map={"positive": "green", "negative": "red", "neutral": "gray"})
    fig.update_layout(bargap=0.2)
    return pio.to_html(fig, full_html=False)

# Plot: Keyword Frequency

def plot_keyword_frequency(keyword_freq_df):
    fig = px.bar(keyword_freq_df, x='Keyword', y=['Title Frequency', 'Snippet Frequency'],
                 title='Keyword Frequency', barmode='group')
    return pio.to_html(fig, full_html=False)

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if USERS.get(username) == password:
            session['user'] = username
            return redirect(url_for('search_page'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/search-page')
def search_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    if 'user' not in session:
        return redirect(url_for('login'))

    query = request.form['query']
    num_results = int(request.form.get('num_results', 10))
    keywords = query.lower().split()

    try:
        results = google_search(query, API_KEY, CSE_ID, num=num_results).get('items', [])
    except Exception as e:
        return render_template("error.html", error=str(e))

    if not results:
        return render_template("error.html", error="No results found.")

    titles = [result['title'] for result in results]
    snippets = [result['snippet'] for result in results]

    df = pd.DataFrame({'Title': titles, 'Snippet': snippets})

    keyword_freq = get_keyword_frequency(results, keywords)
    keyword_freq_df = pd.DataFrame.from_dict(keyword_freq, orient='index').reset_index()
    keyword_freq_df.columns = ['Keyword', 'Title Frequency', 'Snippet Frequency']

    tables_html = render_table_html(df)
    keyword_freq_html = render_table_html(keyword_freq_df)

    sentiments = [TextBlob(snippet).sentiment.polarity for snippet in snippets]
    sentiment_labels = ['positive' if s > 0 else 'negative' if s < 0 else 'neutral' for s in sentiments]
    sentiment_counts = Counter(sentiment_labels)

    sentiment_plot = plot_sentiment_analysis(sentiment_labels)
    keyword_freq_plot = plot_keyword_frequency(keyword_freq_df)

    # Ensure the static folder exists
    os.makedirs("static", exist_ok=True)
    df.to_csv("static/results.csv", index=False)

    return render_template('results.html',
                           tables=tables_html,
                           keyword_freq=keyword_freq_html,
                           sentiment_plot=sentiment_plot,
                           keyword_freq_plot=keyword_freq_plot,
                           sentiment_counts=sentiment_counts,
                           query=query)

@app.route('/download')
def download():
    return send_file("static/results.csv", as_attachment=True)

@app.route('/feedback', methods=['POST'])
def feedback():
    name = request.form.get('name')
    message = request.form.get('message')
    new_feedback = Feedback(name=name, message=message)
    db.session.add(new_feedback)
    db.session.commit()
    flash("Thank you for your feedback!", "success")
    return redirect(url_for('search_page'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)