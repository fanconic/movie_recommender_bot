'''
Telegram Chatbot for movie recommendation

python script app.py that implements an HTTP server using Flask. 
It provides different routes to accept requests to different functions.

Author: fanconic
'''

import time
import json
import logging
import requests
import numpy as np
import pandas as pd
import random
import csv
from flask import Flask, request, jsonify, current_app
from scipy.stats import pearsonr

logging.basicConfig(level= logging.INFO)

# Constant Variables
PORT = 5000
HOST = 'localhost'
API_ENDPOINT = 'localhost:5000'
RATING_PATH = './data/ratings.small.csv'
TITLE_PATH = './data/movies.csv'
LINK_PATH = './data/links.csv'

app = Flask(__name__)

# Create rating matrix, list of users, list of movies
def create_rating_matrix(path):
	df = pd.read_csv(path, sep=',', usecols = ['userId','movieId', 'rating'])
	df = df.pivot(index='userId', columns='movieId', values='rating')
	df = df.fillna(value= 0)
	return df.values, df.index.values, df.columns.values

# Import the titles
def create_titles(path):
	df = pd.read_csv(path, sep=',', usecols = ['movieId', 'title'])
	return df.values

# Import the links
def create_links(path):
	df = pd.read_csv(path, sep=',', usecols = ['movieId', 'imdbId'], dtype={'imdbId': str})
	return df.values

# Create rating matrix, users, movies, titles and links
app.rating_matrix, app.users, app.movies = create_rating_matrix(RATING_PATH)
app.titles = create_titles(TITLE_PATH)
app.links = create_links(LINK_PATH)

# Size down the titles to smaller sample set
temp = []
for title in app.titles:
	if title[0] in app.movies.tolist():
		temp.append(title)
app.titles = np.asarray(temp)

# Size down the links to smaller sample set
temp = []
for link in app.links:
	if link[0] in app.movies.tolist():
		temp.append(link)
app.links = np.asarray(temp)
del temp

# Checks if a User already exists and registers him/her if not
@app.route('/register', methods=['POST'])
def register():
	# Retrieve Data
	data = request.json
	chat_id = data['chat_id']

	# Check if user already exists
	if chat_id in current_app.users.tolist():
		return jsonify({'exists' : 1})
	
	# The chat Id is the new users Id
	current_app.users = np.append(current_app.users, chat_id)

	# Add row of zeros to the rating matrix
	current_app.rating_matrix = np.append(current_app.rating_matrix, np.zeros((1,current_app.rating_matrix.shape[1])), axis=0)
	return jsonify({'exists': 0})

# Get a random movie that hasn't been rated by the user yet
@app.route('/get_unrated_movie', methods=['POST'])
def get_unrated_movie():
	data = request.json
	chat_id = data['chat_id']

	# Get the ratings of a user by its userId
	user_ratings = current_app.rating_matrix[np.where(current_app.users == chat_id)]

	# Get a random movie which is not yet rated
	movieId = current_app.movies[random.choice(np.where(user_ratings == 0)[1])]

	# Create the Title
	title = current_app.titles[np.where(current_app.titles == movieId)[0]][0][1]

	# Create URL
	url = 'https://www.imdb.com/title/tt{}/'.format(current_app.links[np.where(current_app.links == movieId)[0]][0][1])

	return jsonify({
		'id' : str(movieId),
		'title': title,
		'url': url
	})

# Update the ratingsmatrix after the user has rated it
@app.route('/rate_movie', methods=['POST'])
def rate_movie():
	# Retrieve received data
	data = request.json
	chat_id = data['chat_id']
	movieId = int(data['movieId'])
	rating = int(data['rating'])

	# Updated rating matrix
	current_app.rating_matrix[np.where(current_app.users == chat_id), np.where(current_app.movies == movieId)] = rating
	
	'''
	# Write to csv file, so data isn't lost
	row = [str(chat_id), str(movieId), str(rating), 'N/A']

	with open('ratings.small.csv', 'r') as readFile:
		reader = csv.reader(readFile)
		line = list(reader)[-1]
	
		if line != row:
			with open('ratings.small.csv', 'a') as writeFile:
				writer = csv.writer(writeFile)
				writer.writerow(row)
			writeFile.close()
	readFile.close()
	'''

	# Return json string
	return jsonify({'status': 'success'})

# Recommend n movies if the user has rated engough movies
@app.route('/recommend', methods=['POST'])
def recommend():
    	# Retrieve received data
	data = request.json
	chat_id = data['chat_id']
	top_n = data['top_n']

	# Select the ammount of ratings the user has to submit, before getting a recommendation
	N_RATINGS = 10
	
	# Check if the User has recommended at least ten movies
	user_idx = np.where(current_app.users == chat_id)
	user_ratings = current_app.rating_matrix[user_idx]
	if np.where(user_ratings != 0)[1].size < N_RATINGS:
		return jsonify({'movies': []})

	# similarity between users function
	def similarity(u1, u2):
		r, _ = pearsonr(current_app.rating_matrix[u1][0], current_app.rating_matrix[u2])
		return r

	# Create list of index and similarity of the 20 users, with the highest similarity in descending order
	similar_neighbours = []
	for i in range(current_app.users.shape[0]):
  		if i != user_idx:
       			similar_neighbours.append((i, similarity(user_idx, i)))
	similar_neighbours = sorted(similar_neighbours, key=lambda x: x[1], reverse= True)

	#User based collaborative filtering if there are enough recommendations
	# Select the ammount of neighbours to be calculated in the recomendation
	# More neighbours, better prediction, but also more computational time
	N_NEIGHBOURS = 15

	# Create prediction for every single movie with user-based prediction formula
	predictions = []

	# Mean of the ratings of the user
	user_mean = np.mean([r for r in user_ratings[0] if r > 0])

	# Itterate through all the movies
	for movie in current_app.movies:
		prediction = 0
		num = 0
		denom = 0

		# Get the index of the Movie 
		movie_idx = np.where(current_app.movies == movie)

		# Check if the movie has already been rated, if yes, then don't put in prediction
		if current_app.rating_matrix[user_idx, movie_idx] == 0:
			
			# Get all the users which rated the movie
			movie_raters = [neighbour for neighbour in similar_neighbours if current_app.rating_matrix[neighbour[0], movie_idx]  > 0][1:N_NEIGHBOURS+1]

			# Iterate through all the similar neighbours
			for neighbour in movie_raters:

				# index and similarity of the neighbour
				neighbour_idx = neighbour[0]
				neighbour_similarity = neighbour[1]

				# Create the mean of all the ratings of a neighbour
				neighbour_mean = np.mean([r for r in current_app.rating_matrix[neighbour_idx] if r > 0])

				# Get the value the neighbour rated this movie
				neighbour_rating = current_app.rating_matrix[neighbour_idx, movie_idx]

				# Calculate the prediction
				num += neighbour_similarity * (neighbour_rating - neighbour_mean)
				denom += neighbour_similarity
			prediction = user_mean + num / denom
			predictions.append((movie, prediction))
	
	# Sort the predictions and get the top n
	predictions = sorted(predictions, key=lambda x: x[1], reverse= True)[:top_n]
	
	# Create response and jsonify it
	movies = []
	for prediction in predictions:
		movies.append({
			'title': current_app.titles[np.where(current_app.titles == prediction[0])[0]][0][1],
			'url': 'https://www.imdb.com/title/tt{}/'.format(current_app.links[np.where(current_app.links == prediction[0])[0]][0][1])
		})
	return jsonify({'movies': movies})

# Main function to be run
if __name__ == "__main__":
    	app.run(host= HOST, port= PORT)
