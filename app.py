import os
import json
import uuid
import requests
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from dotenv import load_dotenv
import base64
from datetime import datetime, timedelta
import gunicorn
# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "soundroom-secret-key")
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
app.config['LOGO_SVG_PATH'] = 'soundroom.svg'
# Spotify API credentials from .env
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:5000/callback")

# Firebase config from .env
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
FIREBASE_AUTH_DOMAIN = os.getenv("FIREBASE_AUTH_DOMAIN")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET")
FIREBASE_MESSAGING_SENDER_ID = os.getenv("FIREBASE_MESSAGING_SENDER_ID")
FIREBASE_APP_ID = os.getenv("FIREBASE_APP_ID")

@app.route('/')
def index():
    # Pass firebase config to template and current hour
    firebase_config = {
        'apiKey': FIREBASE_API_KEY,
        'authDomain': FIREBASE_AUTH_DOMAIN,
        'projectId': FIREBASE_PROJECT_ID,
        'storageBucket': FIREBASE_STORAGE_BUCKET,
        'messagingSenderId': FIREBASE_MESSAGING_SENDER_ID,
        'appId': FIREBASE_APP_ID
    }
    current_hour = datetime.now().hour
    return render_template('index.html', firebase_config=firebase_config, current_hour=current_hour)
@app.route('/my-rooms')
def my_rooms():
    if not session.get('logged_in'):
        return redirect('/')
    firebase_config = {
        'apiKey': FIREBASE_API_KEY,
        'authDomain': FIREBASE_AUTH_DOMAIN,
        'projectId': FIREBASE_PROJECT_ID,
        'storageBucket': FIREBASE_STORAGE_BUCKET,
        'messagingSenderId': FIREBASE_MESSAGING_SENDER_ID,
        'appId': FIREBASE_APP_ID
    }
    current_hour = datetime.now().hour
    return render_template('my_rooms.html', firebase_config=firebase_config, current_hour=current_hour)

@app.route('/room/<room_id>')
def room(room_id):
    if not session.get('logged_in'):
        return redirect('/')
    firebase_config = {
        'apiKey': FIREBASE_API_KEY,
        'authDomain': FIREBASE_AUTH_DOMAIN,
        'projectId': FIREBASE_PROJECT_ID,
        'storageBucket': FIREBASE_STORAGE_BUCKET,
        'messagingSenderId': FIREBASE_MESSAGING_SENDER_ID,
        'appId': FIREBASE_APP_ID
    }
    current_hour = datetime.now().hour
    return render_template('room.html', room_id=room_id, firebase_config=firebase_config, current_hour=current_hour)

@app.route('/album/<room_id>/<album_id>')
def album_detail(room_id, album_id):
    if not session.get('logged_in'):
        return redirect('/')
    firebase_config = {
        'apiKey': FIREBASE_API_KEY,
        'authDomain': FIREBASE_AUTH_DOMAIN,
        'projectId': FIREBASE_PROJECT_ID,
        'storageBucket': FIREBASE_STORAGE_BUCKET,
        'messagingSenderId': FIREBASE_MESSAGING_SENDER_ID,
        'appId': FIREBASE_APP_ID
    }
    current_hour = datetime.now().hour
    return render_template('album.html', room_id=room_id, album_id=album_id, firebase_config=firebase_config, current_hour=current_hour)
@app.route('/spotify/auth')
def spotify_auth():
    scope = "user-read-private user-read-email user-library-read"
    auth_url = f"https://accounts.spotify.com/authorize?response_type=code&client_id={SPOTIFY_CLIENT_ID}&scope={scope}&redirect_uri={SPOTIFY_REDIRECT_URI}"
    return redirect(auth_url)
# Add these new routes to your Flask application

@app.route('/api/recommendations')
def get_recommendations():
    # print("================ RECOMMENDATIONS REQUEST STARTED ================")
    
    if not session.get('logged_in'):
        print("Error: User not logged in")
        return jsonify({'error': 'Authentication required'})
        
    # Check if token is valid
    if 'spotify_token_info' not in session or session.get('token_expiry', 0) < datetime.now().timestamp():
        print("Error: Spotify token missing or expired")
        try:
            refresh_token(session.get('spotify_token_info', {}).get('refresh_token'))
            # print("Successfully refreshed token")
            token_info = session['spotify_token_info']
        except:
            return jsonify({'error': 'Spotify authentication required', 'auth_url': url_for('spotify_auth')})
    else:
        token_info = session['spotify_token_info']
    
    # Get room_id and album_ids from request to exclude existing albums
    room_id = request.args.get('room_id')
    album_ids = request.args.get('album_ids', '')
    existing_album_ids = album_ids.split(',') if album_ids and ',' in album_ids else [album_ids] if album_ids else []
    
    # print(f"Will exclude {len(existing_album_ids)} existing albums")
    
    # Список популярных хип-хоп исполнителей (конкретные имена вместо поисковых запросов)
    popular_artists = [
        "Drake",
        "Kendrick Lamar",
        "Travis Scott",
        "Future",
        "Lil Baby",
        "Lil Uzi Vert",
        "21 Savage",
        "Young Thug",
        "J. Cole",
        "A$AP Rocky",
        "Tyler, The Creator",
        "Megan Thee Stallion",
        "Gunna",
        "Roddy Ricch",
        "Metro Boomin",
        "Juice WRLD",
        "Pop Smoke",
        "Jack Harlow",
        "Kid Cudi",
        "Cardi B",
        "Don Toliver"
    ]
    
    all_albums = []
    search_errors = 0
    
    # Ищем альбомы от популярных артистов
    for artist in popular_artists:
        if len(all_albums) >= 40:
            break  # У нас достаточно альбомов
            
        if search_errors >= 5:
            break  # Слишком много ошибок, прекращаем попытки
        
        try:
            print(f"Searching albums for artist: {artist}")
            search_url = f"https://api.spotify.com/v1/search?q=artist:{artist}&type=album&limit=3"
            
            response = requests.get(
                search_url,
                headers={
                    'Authorization': f"Bearer {token_info['access_token']}"
                }
            )
            
            if response.status_code == 200:
                search_data = response.json()
                albums = search_data.get('albums', {}).get('items', [])
                
                # Отфильтруем только настоящие альбомы (не сборники/компиляции)
                filtered_albums = []
                for album in albums:
                    # Проверим, что это альбом конкретного артиста, а не компиляция
                    if album.get('album_type') in ['album', 'single'] and len(album.get('artists', [])) > 0:
                        # Проверим, что первый артист - именно тот, кого мы искали
                        if album['artists'][0]['name'].lower() == artist.lower() or artist.lower() in album['artists'][0]['name'].lower():
                            filtered_albums.append(album)
                
                all_albums.extend(filtered_albums)
                # print(f"Found {len(filtered_albums)} albums for artist '{artist}'")
            elif response.status_code == 401:
                # Токен недействителен, пытаемся обновить
                try:
                    refresh_token(session.get('spotify_token_info', {}).get('refresh_token'))
                    token_info = session['spotify_token_info']
                    print("Token refreshed, retrying search")
                    continue
                except:
                    print("Failed to refresh token")
                    search_errors += 1
            else:
                print(f"Error searching for '{artist}': {response.status_code}")
                search_errors += 1
        except Exception as e:
            print(f"Exception during search for '{artist}': {str(e)}")
            search_errors += 1
    
    # Если у нас все еще недостаточно альбомов, попробуем альбомы из чартов хип-хопа
    if len(all_albums) < 15:
        try:
            print("Not enough albums, trying to get new hip-hop releases")
            search_url = "https://api.spotify.com/v1/search?q=genre:hip-hop year:2023-2024&type=album&limit=10"
            
            response = requests.get(
                search_url,
                headers={
                    'Authorization': f"Bearer {token_info['access_token']}"
                }
            )
            
            if response.status_code == 200:
                search_data = response.json()
                albums = search_data.get('albums', {}).get('items', [])
                
                # Фильтруем компиляции и сборники
                filtered_albums = []
                for album in albums:
                    if album.get('album_type') in ['album', 'single'] and len(album.get('artists', [])) > 0:
                        # Имя артиста не должно содержать "various" или "compilation"
                        artist_name = album['artists'][0]['name'].lower()
                        if "various" not in artist_name and "compilation" not in artist_name and "mixtape" not in artist_name:
                            filtered_albums.append(album)
                
                all_albums.extend(filtered_albums)
                print(f"Found {len(filtered_albums)} additional hip-hop albums")
            else:
                print(f"Error searching new hip-hop releases: {response.status_code}")
        except Exception as e:
            print(f"Exception during search for new hip-hop releases: {str(e)}")
    
    # Удаляем дубликаты и исключаем альбомы, которые уже в комнате
    unique_albums = []
    seen_album_ids = set()
    
    for album in all_albums:
        if album['id'] not in seen_album_ids and album['id'] not in existing_album_ids:
            unique_albums.append(album)
            seen_album_ids.add(album['id'])
    
    # Берем первые 20 альбомов
    final_albums = unique_albums[:20]
    
    print(f"After removing duplicates and existing albums, returning {len(final_albums)} unique albums")
    
    if len(final_albums) < 8:
        print(f"WARNING: Could only find {len(final_albums)} albums - less than the minimum 8")
    
    print("================ RECOMMENDATIONS REQUEST COMPLETED ================")
    return jsonify({'albums': final_albums})
@app.route('/api/delete-room', methods=['POST'])
def delete_room():
    if not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'})
    
    data = request.json
    room_id = data.get('room_id')
    
    # Get the current user ID
    current_user_id = "spotify:" + session.get('spotify_user', {}).get('id', '')
    
    # In a real implementation, you would first check if the user is the creator
    # Then delete the room from the database
    return jsonify({
        'status': 'success',
        'message': 'Room deleted successfully'
    })


# Функция для обновления токена
def refresh_token(refresh_token):
    if not refresh_token:
        raise Exception("No refresh token available")
    
    auth_options = {
        'url': 'https://accounts.spotify.com/api/token',
        'data': {
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        },
        'headers': {
            'Authorization': 'Basic ' + base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode(),
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    }
    
    response = requests.post(
        auth_options['url'], 
        data=auth_options['data'], 
        headers=auth_options['headers']
    )
    
    if response.status_code == 200:
        token_info = response.json()
        
        # Сохраняем refresh_token, который может не вернуться в новом ответе
        if 'refresh_token' not in token_info:
            token_info['refresh_token'] = refresh_token
            
        session['spotify_token_info'] = token_info
        session['token_expiry'] = datetime.now().timestamp() + token_info['expires_in']
        
        return token_info
    else:
        raise Exception(f"Failed to refresh token: {response.status_code}")


@app.route('/api/update-room', methods=['POST'])
def update_room():
    if not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'})
    
    data = request.json
    room_id = data.get('room_id')
    room_name = data.get('name')
    
    # In a real implementation, you would update the room in the database
    # Here we just return success for demonstration
    return jsonify({
        'status': 'success',
        'message': 'Room updated successfully'
    })

@app.route('/api/add-member', methods=['POST'])
def add_member():
    if not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'})
    
    data = request.json
    room_id = data.get('room_id')
    member_id = data.get('member_id')
    
    # In a real implementation, you would add the member to the database
    # Here we just return success for demonstration
    return jsonify({
        'status': 'success',
        'message': 'Member added successfully'
    })

@app.route('/api/remove-member', methods=['POST'])
def remove_member():
    if not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'})
    
    data = request.json
    room_id = data.get('room_id')
    member_id = data.get('member_id')
    
    # In a real implementation, you would remove the member from the database
    # Here we just return success for demonstration
    return jsonify({
        'status': 'success',
        'message': 'Member removed successfully'
    })

@app.route('/api/remove-album', methods=['POST'])
def remove_album():
    if not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'})
    
    data = request.json
    room_id = data.get('room_id')
    album_id = data.get('album_id')
    
    # In a real implementation, you would remove the album from the database
    # Here we just return success for demonstration
    return jsonify({
        'status': 'success',
        'message': 'Album removed successfully'
    })
@app.route('/callback')
def spotify_callback():
    code = request.args.get('code')
    
    # Exchange authorization code for access token
    auth_options = {
        'url': 'https://accounts.spotify.com/api/token',
        'data': {
            'code': code,
            'redirect_uri': SPOTIFY_REDIRECT_URI,
            'grant_type': 'authorization_code'
        },
        'headers': {
            'Authorization': 'Basic ' + base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode(),
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    }
    
    try:
        response = requests.post(
            auth_options['url'], 
            data=auth_options['data'], 
            headers=auth_options['headers']
        )
        
        token_info = response.json()
        
        if 'access_token' in token_info:
            # Store token info in session
            session['spotify_token_info'] = token_info
            session['token_expiry'] = datetime.now().timestamp() + token_info['expires_in']
            
            # Get user info from Spotify
            user_response = requests.get(
                'https://api.spotify.com/v1/me',
                headers={
                    'Authorization': f"Bearer {token_info['access_token']}"
                }
            )
            
            if user_response.status_code == 200:
                spotify_user = user_response.json()
                session['spotify_user'] = spotify_user
                session['logged_in'] = True
                print(f"User logged in: {spotify_user.get('display_name')}")
                
            return redirect('/')
        else:
            print(f"Error getting token: {token_info}")
            return jsonify({'error': 'Failed to obtain access token'})
    except Exception as e:
        print(f"Exception in callback: {str(e)}")
        return jsonify({'error': f'Exception: {str(e)}'})

@app.route('/logout')
def logout():
    # Clear session
    session.clear()
    return redirect('/')

@app.route('/api/search-album', methods=['GET'])
def search_album():
    if not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'})
        
    query = request.args.get('q')
    
    if not query:
        return jsonify({'error': 'No search query provided'})
    
    # Check if token is valid
    if 'spotify_token_info' not in session or session.get('token_expiry', 0) < datetime.now().timestamp():
        return jsonify({'error': 'Spotify authentication required', 'auth_url': url_for('spotify_auth')})
    
    token_info = session['spotify_token_info']
    
    # Search for albums
    search_url = f"https://api.spotify.com/v1/search?q={query}&type=album&limit=10"
    response = requests.get(
        search_url,
        headers={
            'Authorization': f"Bearer {token_info['access_token']}"
        }
    )
    
    search_results = response.json()
    return jsonify(search_results)

@app.route('/api/album/<album_id>')
def get_album(album_id):
    if not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'})
        
    # Check if token is valid
    if 'spotify_token_info' not in session or session.get('token_expiry', 0) < datetime.now().timestamp():
        return jsonify({'error': 'Spotify authentication required', 'auth_url': url_for('spotify_auth')})
    
    token_info = session['spotify_token_info']
    
    # Get album details
    album_url = f"https://api.spotify.com/v1/albums/{album_id}"
    response = requests.get(
        album_url,
        headers={
            'Authorization': f"Bearer {token_info['access_token']}"
        }
    )
    
    album_data = response.json()
    
    # Get album tracks
    tracks_url = f"https://api.spotify.com/v1/albums/{album_id}/tracks"
    tracks_response = requests.get(
        tracks_url,
        headers={
            'Authorization': f"Bearer {token_info['access_token']}"
        }
    )
    
    tracks_data = tracks_response.json()
    
    return jsonify({
        'album': album_data,
        'tracks': tracks_data
    })

@app.route('/api/create-room', methods=['POST'])
def create_room():
    if not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'})
        
    data = request.json
    room_name = data.get('room_name')
    creator_id = "spotify:" + session.get('spotify_user', {}).get('id', '')
    
    room_id = str(uuid.uuid4())[:8]
    
    # In a real implementation, you would save the room to a database
    # Here we just return the room ID
    return jsonify({
        'status': 'success',
        'room_id': room_id,
        'creator_id': creator_id,
        'invite_link': f"{request.host_url}room/{room_id}"
    })

@app.route('/api/add-rating', methods=['POST'])
def add_rating():
    if not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'})
        
    data = request.json
    room_id = data.get('room_id')
    album_id = data.get('album_id')
    ratings = data.get('ratings')
    comment = data.get('comment')
    
    user_id = "spotify:" + session.get('spotify_user', {}).get('id', '')
    
    # Calculate overall rating (average of all category ratings)
    overall_rating = 0
    rating_count = 0
    
    for category, value in ratings.items():
        if value and isinstance(value, (int, float)):
            overall_rating += value
            rating_count += 1
    
    # Calculate average if there are ratings
    if rating_count > 0:
        overall_rating = round(overall_rating / rating_count, 1)
    else:
        overall_rating = None
    
    # Add overall rating to the ratings object
    ratings['overall'] = overall_rating
    
    # Create rating document data
    rating_data = {
        'roomId': room_id,
        'albumId': album_id,
        'userId': user_id,
        'rating': ratings,
        'comment': comment,
        'timestamp': datetime.now().isoformat()
    }
    
    # In a real implementation with Firebase, you would save this data
    # to the 'ratings' collection
    # Here we just return success for demonstration
    return jsonify({
        'status': 'success',
        'message': 'Rating added successfully',
        'data': rating_data
    })
@app.route('/api/user-info')
def user_info():
    """Return current user info from session (for debugging)"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not logged in'})
    
    return jsonify({
        'spotify_user': session.get('spotify_user'),
        'logged_in': session.get('logged_in'),
        'token_expiry': session.get('token_expiry')
    })

if __name__ == '__main__':
    app.run(debug=True)