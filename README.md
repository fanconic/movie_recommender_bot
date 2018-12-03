# Movie Recommender Bot
Telegram Bot that recommends movies.


This bot is implemented in python and uses User Collaborative Filtering to give movie recommendations.
The Python Flask dictionary was used to establish a HTTP connection between app.py and bot.py.


The Telegram bot takes 3 commands from as messages:

/start: registers the users in the recommmendation DB

/rate : returns a random unrated movie, which can be rated from 1 to 5

/recommend: Recommends the three best fitting movies for the user.


Have fun!

fanconic
