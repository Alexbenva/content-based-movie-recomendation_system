import os
from datetime import timedelta

class Config:
    """Base configuration class."""
    
    # Basic Flask config
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = False
    TESTING = False
    
    # API Keys
    TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
    OMDB_API_KEY = os.environ.get('OMDB_API_KEY')
    
    # ML Model settings
    ARTIFACTS_PATH = os.path.join('ml_model', 'artifacts')
    MODEL_CACHE_SIZE = 128
    
    # API Rate limiting
    API_RATE_LIMITS = {
        'tmdb': {'calls': 40, 'period': 10},  # 40 calls per 10 seconds
        'omdb': {'calls': 1000, 'period': 10}  # 1000 calls per 10 seconds
    }
    
    # Request timeouts
    API_TIMEOUT = 10  # seconds
    
    # Recommendation settings
    DEFAULT_RECOMMENDATIONS = 10
    MAX_RECOMMENDATIONS = 50
    MIN_RECOMMENDATIONS = 1
    
    # Caching
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes
    
    # Logging
    LOG_LEVEL = 'INFO'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # CORS settings
    CORS_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']
    
    # File upload settings (for future features)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = 'uploads'
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    
    # Database settings (for future use)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    
    # Feature flags
    FEATURES = {
        'api_search': True,
        'collaborative_filtering': True,
        'clustering_recommendations': True,
        'genre_preferences': True,
        'popularity_boost': True,
        'diversity_enhancement': True
    }
    
    @staticmethod
    def init_app(app):
        """Initialize app with this config."""
        pass

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    
    # More lenient CORS for development
    CORS_ORIGINS = ['*']
    
    # Shorter cache timeout for development
    CACHE_DEFAULT_TIMEOUT = 60
    
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        
        # Development-specific initialization
        import logging
        logging.basicConfig(
            level=logging.DEBUG,
            format=Config.LOG_FORMAT
        )

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    LOG_LEVEL = 'INFO'
    
    # Production database URL (for future use)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(__file__), 'movie_recommender.db')
    
    # Security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Stricter CORS
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '').split(',') if os.environ.get('CORS_ORIGINS') else []
    
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        
        # Production-specific initialization
        import logging
        from logging.handlers import RotatingFileHandler
        
        # Set up file logging
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler(
            'logs/movie_recommender.log', 
            maxBytes=10240000, 
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(Config.LOG_FORMAT))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Movie Recommender startup')

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    
    # Use in-memory database for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Shorter timeouts for testing
    API_TIMEOUT = 5
    CACHE_DEFAULT_TIMEOUT = 10
    
    # Mock API keys for testing
    TMDB_API_KEY = 'test_tmdb_key'
    OMDB_API_KEY = 'test_omdb_key'

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment."""
    env = os.environ.get('FLASK_ENV', 'default')
    return config.get(env, config['default'])