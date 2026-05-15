from flask import Flask, render_template

app = Flask(__name__)

# Route für die Startseite
@app.route('/')
def home():
    return render_template('index.html')

# Route für eine reine "Über uns" Seite (falls du später Tabs willst)
@app.route('/about')
def about():
    return render_template('about.html')

# Route für den Driver Hub (als Platzhalter)
@app.route('/hub')
def hub():
    return "<h1>Willkommen im Driver Hub! (spätere Implementierung baue hub)</h1>"

if __name__ == '__main__':
    # Startet den Webserver
    app.run(debug=True, port=6000)