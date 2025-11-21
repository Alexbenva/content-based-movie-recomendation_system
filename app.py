from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import os
from datetime import datetime
import traceback

# Import ML model and services
from ml_model.recommend import MovieRecommender
from services.movie_apis import MovieAPIService
from config import Config

from dotenv import load_dotenv
load_dotenv()

# ========================================
# Flask App Initialization
# ========================================
app = Flask(__name__)
app.config.from_object(Config)

# Enable CORS (support for both HTTP & HTTPS localhost)
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "http://localhost:3000",
            "https://localhost:3000",
            "http://127.0.0.1:3000"
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# ========================================
# Logging Configuration
# ========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========================================
# Global Variables
# ========================================
movie_recommender = None
api_service = None
startup_done = False


# ========================================
# Initialization
# ========================================
def initialize_services():
    """Initialize ML recommender and external APIs."""
    global movie_recommender, api_service
    try:
        artifacts_path = os.path.join('ml_model', 'artifacts')
        if not os.path.exists(artifacts_path):
            logger.error(f"Artifacts path not found: {artifacts_path}")
            return False

        movie_recommender = MovieRecommender(artifacts_path=artifacts_path)
        logger.info("✅ Movie recommender initialized successfully")

        api_service = MovieAPIService()
        logger.info("✅ External API service initialized successfully")

        return True

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        traceback.print_exc()
        return False


@app.before_request
def startup():
    """Initialize all services before first request."""
    global startup_done
    if not startup_done:
        logger.info("🚀 Initializing backend services...")
        if not initialize_services():
            logger.error("⚠️ Service initialization failed — limited functionality.")
        else:
            logger.info("✅ All services initialized successfully!")
        startup_done = True


# ========================================
# Routes
# ========================================

@app.route('/api/search', methods=['POST', 'OPTIONS'])
def api_search():
    """Search for a movie and return recommendations."""
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        logger.info(f"🎬 Received search request: {data}")

        if not data or 'movie_name' not in data:
            return jsonify({'error': 'Movie name is required', 'status': 'error'}), 400

        movie_name = data['movie_name'].strip()
        n_recommendations = data.get('n_recommendations', 10)
        preference_genres = data.get('preference_genres', [])

        if not movie_name:
            return jsonify({'error': 'Movie name cannot be empty', 'status': 'error'}), 400

        # Validate recommendation count
        if not isinstance(n_recommendations, int) or not (1 <= n_recommendations <= 50):
            n_recommendations = 10

        if movie_recommender is None:
            logger.error("❌ Movie recommender not initialized.")
            return jsonify({'error': 'Recommendation service unavailable', 'status': 'error'}), 503

        # Get recommendations
        logger.info(f"🔍 Searching for movie: {movie_name}")
        results = movie_recommender.get_recommendations(
            movie_name,
            n_recommendations=n_recommendations,
            preference_genres=preference_genres if hasattr(movie_recommender, '_apply_genre_preferences') else None
        )

        # 🔄 Normalize backend response for React frontend
        response = {
            "movie": results.get("searched_movie", {}),
            "recommendations": results.get("recommendations", []),
            "status": results.get("status", "success")
        }

        logger.info(f"✅ Recommendations ready for '{movie_name}'")
        return jsonify(response)

    except Exception as e:
        logger.error(f"🔥 Error in /api/search: {e}")
        traceback.print_exc()
        return jsonify({
            'error': 'An internal server error occurred',
            'status': 'error',
            'details': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """API health check."""
    try:
        status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': {
                'movie_recommender': movie_recommender is not None,
                'api_service': api_service is not None
            }
        }
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


# ========================================
# Error Handlers
# ========================================
@app.errorhandler(404)
def not_found_error(error):
    if request.path.startswith('/api/'):
        return jsonify({
            'error': 'Endpoint not found',
            'status': 'error',
            'path': request.path
        }), 404
    return "Not Found", 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    if request.path.startswith('/api/'):
        return jsonify({
            'error': 'Internal server error',
            'status': 'error'
        }), 500
    return "Internal Server Error", 500


# ========================================
# App Entry Point
# ========================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))

    print("=" * 60)
    print("🎬 Starting Movie Recommendation Backend")
    print(f"📡 URL: http://127.0.0.1:{port}")
    print(f"🔗 API: http://127.0.0.1:{port}/api/search")
    print("=" * 60)

    app.run(
        host='0.0.0.0',
        port=port,
        debug=True,
        threaded=True
    )
