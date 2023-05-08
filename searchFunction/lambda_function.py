import json
import os
import requests
import boto3
from botocore.exceptions import ClientError
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

REGION = 'us-east-1'
HOST = 'search-myshows-zmfz4todbf2x2pu6a5oaajngpi.us-east-1.es.amazonaws.com'
INDEX = 'tvshows'
API_KEY= '1c61bfaa656d0222aec46816f8e9eccc'


def lambda_handler(event, context):
    print('Received event: ' + json.dumps(event))
    showName = event.get('queryStringParameters', event).get('show', None)


    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('showid_showname')
    
    response = table.query(
    IndexName='showname-index',
    KeyConditionExpression=boto3.dynamodb.conditions.Key('showname').eq(showName))
    
    result = response['Items']
    result_from_db = []

    if (len(result) != 0):
        for each_show in result:
 
            movie_id = each_show['showId']
            result_from_db.append(lookup_data({"MovieID": "{}".format(movie_id)}))
        
    
        # return result_from_db
    else:
        result = call_api_search_movies(showName)
        for movie in result:
            data = store_movie_dynamo(movie)
            store_showId_showName(movie)
            result_from_db.append(data)
   


    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': '*',
        },
        'body': json.dumps({'results': result_from_db}, default=str)
    }
    
    
def store_movie_openSearch(movie):
    movie_data = {
        'movie_id': movie['id'],
        'movie_name': movie['original_title']
    }

    index_name = 'movies'  # Modify this value to match your OpenSearch index name

    os_client.index(index=index_name, id=movie['id'], body=movie_data)
    
def get_movie_credits(movie_id):
    url = f'https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={API_KEY}'
    response = requests.get(url)
    data = response.json()
    return data
    
def get_movie_details(movie_id):
    url = f'https://api.themoviedb.org/3/movie/{movie_id}?api_key={API_KEY}'
    response = requests.get(url)
    data = response.json()
    return data

def get_movie_keywords(movie_id):
    url = f'https://api.themoviedb.org/3/movie/{movie_id}/keywords?api_key={API_KEY}'
    response = requests.get(url)
    data = response.json()
    return data
    
def store_movie_dynamo(movie):
    details = get_movie_details(movie['id'])
    credits = get_movie_credits(movie['id'])
    keywords = get_movie_keywords(movie['id'])


    # Extract director and actors
    director = ''
    actors = []
    for person in credits['crew']:
        if person['job'] == 'Director':
            director = person['name']
            break

    for actor in credits['cast'][:5]:
        actors.append(actor['name'])

        
    movie_data = {
        'MovieID': str(movie['id']),
        'MovieTitle': movie['original_title'],
        'ReleaseYear': movie['release_date'],
        'Genres': [genre['name'] for genre in details['genres']],
        'Director': director,
        'Actors': actors,
        'Language': details['spoken_languages'][0]['english_name'],
        'Overview': details['overview'],
        'Keywords': [keyword['name'] for keyword in keywords['keywords']]
    }

    db = boto3.resource('dynamodb')
    table = db.Table('show_data')
    
    table.put_item(Item=movie_data)
    return movie_data

def store_showId_showName(movie):
        movie_data = {
        'showId': str(movie['id']),
        'showname': movie['original_title']}

        db = boto3.resource('dynamodb')
        table = db.Table('showid_showname')
        table.put_item(Item=movie_data)
        
    

# return top 3 movies with movie_name   
def call_api_search_movies(movie_name):


    url = f'https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={movie_name}'

    response = requests.get(url)
    if response.status_code == 200:
        results = response.json()['results']
        return results[:5]
    else:
        print("Error retrieving data from TMDB API")
        
    
def lookup_data(key, db=None, table='show_data'):
    if not db:
        db = boto3.resource('dynamodb')
    table = db.Table(table)
    try:
        response = table.get_item(Key={'MovieID': key['MovieID']})
    except ClientError as e:
        print('Error', e.response['Error']['Message'])
    else:
        return response['Item']
        


def get_awsauth(region, service):
    cred = boto3.Session().get_credentials()
    return AWS4Auth(cred.access_key,
                    cred.secret_key,
                    region,
                    service,
                    session_token=cred.token)
