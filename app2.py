################################## importing required module and packages #####################################################


from flask import Flask, render_template, request, redirect, url_for,session
import requests
import nltk
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from authlib.integrations.flask_client import OAuth
from bs4 import BeautifulSoup
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.tag import pos_tag
from collections import Counter
import psycopg2  #DB connection
import json
import re

nltk.download('averaged_perceptron_tagger')
nltk.download("stopwords")
nltk.download("punkt")
nltk.download('universal_tagset')

########################################  Flask Instance and DB connection  and Table creation  #################################
database_url = "dpg-cnmn6gmn7f5s73d7s5f0-a.oregon-postgres.render.com"
host = f"{database_url}"
app = Flask(__name__)
def connect_db():
    conn = psycopg2.connect(
        dbname="dhp2024_muqf",
        user="dhp2024_muqf_user",
        password="VDnibngKxYSg9RYrQRNEdKz0QFm2f0v6",
        host=host
    )
    return conn

conn = connect_db()

#postgres://dhp2024_muqf_user:VDnibngKxYSg9RYrQRNEdKz0QFm2f0v6@dpg-cnmn6gmn7f5s73d7s5f0-a/dhp2024_muqf

cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS news_data (
        url TEXT,
        title varchar,
        newstype TEXT,
        count_stop INT,
        num_sentences INT,
        num_words INT,
        pos_tags JSON,
        reading_time_minutes FLOAT,
        summary varchar            
    )
""")
conn.commit()


########################################  Cleaning and Extraction part ########################################################


stopwords = nltk.corpus.stopwords.words('english')

def text_cleaning(url):
    response = requests.get(url)
    html_content = response.text
    soup = BeautifulSoup(html_content, 'html.parser')
    titles = soup.title.text
    # Extracting title before '|'
    title = re.search(r'^(.*?)\|', titles).group(1).strip()

    # Extracting news type between '|' and '-'
    news_type = re.search(r'\|(.*?)\-', titles).group(1).strip()

    p_tags = soup.find('div', {'class': 'story_details'}).find_all('p')
    texts = ''
    for p_tag in p_tags:
        texts += p_tag.get_text() + ' '  # Add a space between paragraphs
        count_stop=0
    # Define a regular expression pattern to match sentences containing '@' or '#'
    pattern = r'.*[@#].*[\.\?!](?=\s|$)'

    # Use re.sub() to replace matching sentences with an empty string
    cleaned_text = re.sub('.*[@#$].*[\.\?!](?=\s|$)', '', texts)
    # stopwords = set(stopwords.words("english"))
    count_stop=0
    for word in cleaned_text :
        if word in stopwords:
            count_stop+=1
    sentences = sent_tokenize(cleaned_text)
    num_sentences = len(sentences)
    words = word_tokenize(cleaned_text.lower())
    num_words = len(words)
    pos_tags = pos_tag(words,tagset="universal")
    pos_counts = Counter(tag for word, tag in pos_tags)  
    summary = summarize_news(cleaned_text)
    reading_time_minutes=estimate_reading_time(cleaned_text)
    return title,news_type,summary, cleaned_text,num_sentences,count_stop, num_words, pos_counts,reading_time_minutes
def estimate_reading_time(text, words_per_minute = 100):
    # Count the number of words in the text
    words = re.findall(r'\w+', text)
    word_count = len(words)
    # Estimate the reading time based on the average reading speed
    reading_time_minutes = word_count / words_per_minute
    return reading_time_minutes


def summarize_news(text):
    # Initialize a parser with the provided text
    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    # Initialize an LsaSummarizer
    summarizer = LsaSummarizer()
    # Summarize the text with the summarizer
    summary = summarizer(parser.document, 10)  # Specify the number of sentences in the summary
    # Convert the summary sentences to a single string
    summary_text = " ".join(str(sentence) for sentence in summary)
    return summary_text


stopwords = nltk.corpus.stopwords.words('english')

# helper function
def POS(pos_tag):
    return  json.dumps(dict(pos_tag))


# Function to store URL, news text, and analysis summary in PostgreSQL database
def store_data(url,title ,newstype ,num_sentences,num_words,count_stop,pos_tags,reading_time_minutes ,summary ):
    pos_tags = POS(pos_tags)
    cursor.execute("INSERT INTO news_data (url,title ,newstype ,num_sentences,num_words,count_stop,pos_tags,reading_time_minutes ,summary) VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s)", 
    (url,title ,newstype ,num_sentences,num_words,count_stop,pos_tags,reading_time_minutes ,summary))
    conn.commit()



# Route for home page
@app.route('/')
def index():
    return render_template('index.html')


# Route for submitting URL
@app.route('/submit', methods=['GET','POST'])
def submit():
    if request.form['submit'] == 'abc':
        url = request.form['url']
        print(url)
        try:
            # Check if the URL contains the required term
            if 'https://indianexpress.com/article/' not in url:
            
            # if 'https://timesofindia.indiatimes.com/' not in url:
                # Render a template with a message for incorrect URL
                errors='PLEASE put the URL of indian express'
                return render_template('index.html',errors=errors)
            
            # If the URL is correct, proceed with data extraction and storage
            title, newstype, summary, cleaned_text, count_stop, num_sentences, num_words, pos_tags, reading_time_minutes = text_cleaning(url)
            store_data(url, title, newstype, num_sentences, num_words, count_stop, pos_tags, reading_time_minutes, summary)
            return render_template('index.html', summary=summary, cleaned_text=cleaned_text, num_sentences=num_sentences, num_words=num_words, pos_tags=pos_tags, title=title, count_stop=count_stop, newstype=newstype, reading_time_minutes=reading_time_minutes)
        
        except Exception as e:
            # Handle any exceptions and render an error template
            errors='please input the correct URL'
            return render_template('index.html',errors=errors)
           
    
    return render_template('index.html')


####################################################################### Admin Authentication part  ##########################################################

oauth = OAuth(app)
app.config['SECRET_KEY'] = "Dak@blru22"
app.config['GITHUB_CLIENT_ID'] = "43d8664048493013adcb"
app.config['GITHUB_CLIENT_SECRET'] = "967933b6faaefe9f44615c071821e79f50e7c4ff"

github = oauth.register(
    name='github',
    client_id=app.config["GITHUB_CLIENT_ID"],
    client_secret=app.config["GITHUB_CLIENT_SECRET"],
    access_token_url='https://github.com/login/oauth/access_token',
    access_token_params=None,
    authorize_url='https://github.com/login/oauth/authorize',
    authorize_params=None,
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'},
)


@app.route('/history')
def history():
    # Retrieve stored data from PostgreSQL
    cursor.execute("SELECT * FROM news_data")
    data = cursor.fetchall()
    return render_template('history.html', data=data)
# Github login route
@app.route('/login/github')
def github_login():
    github = oauth.create_client('github')
    redirect_uri = url_for('github_authorize', _external=True)
    return github.authorize_redirect(redirect_uri)

# Github authorize route
@app.route('/login/github/authorize')
def github_authorize():
    github = oauth.create_client('github')
    token = github.authorize_access_token()
    session['github_token'] = token
    resp = github.get('user').json()
    print(f"\n{resp}\n")
    # connection = connect_to_database()
    # cursor = connection.cursor()

    cursor.execute("SELECT * FROM news_data")
    data = cursor.fetchall()
    return render_template('history.html', data=data)
    # Redirect to a template or another route after successful authorization

# Logout route for GitHub
@app.route('/logout/github')
def github_logout():
    session.pop('github_token', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True,host = '0.0.0.0')
