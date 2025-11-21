import joblib
import numpy as np
import pandas as pd
import requests
import os
from typing import List, Dict, Optional
import logging
from functools import lru_cache

class MovieRecommender:
    def __init__(self, artifacts_path='D:/ml project/movie_recommender_backend/ml_model/artifacts/'):
        """Initialize the recommender system with pre-trained models."""
        self.artifacts_path = artifacts_path
        self.setup_logging()
        self.load_models()
        self.setup_api_keys()
        
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_api_keys(self):
        """Setup API keys from environment variables."""
        self.tmdb_api_key = os.getenv('TMDB_API_KEY')
        self.omdb_api_key = os.getenv('OMDB_API_KEY')
        
        if not self.tmdb_api_key:
            self.logger.warning("TMDB_API_KEY not found in environment variables")
        if not self.omdb_api_key:
            self.logger.warning("OMDB_API_KEY not found in environment variables")
    
    def load_models(self):
        """Load pre-trained models and data."""
        try:
            self.tfidf_vectorizer = joblib.load(os.path.join(self.artifacts_path, 'tfidf_vectorizer.pkl'))
            self.svd_model = joblib.load(os.path.join(self.artifacts_path, 'svd_model.pkl'))  # <-- Load SVD
            self.kmeans_model = joblib.load(os.path.join(self.artifacts_path, 'kmeans_model.pkl'))
            self.movies_df = joblib.load(os.path.join(self.artifacts_path, 'movies_preprocessed.pkl'))
            
            if not isinstance(self.movies_df, pd.DataFrame):
                self.movies_df = pd.DataFrame(self.movies_df)
            
            if 'combined_features' not in self.movies_df.columns:
                self.movies_df['combined_features'] = self._create_combined_features()
            
            # Pre-compute TF-IDF matrix
            tfidf_matrix_full = self.tfidf_vectorizer.transform(
                self.movies_df['combined_features'].fillna('')
            )

            # Apply SVD for dimensionality reduction
            self.tfidf_matrix = self.svd_model.transform(tfidf_matrix_full)
            self.logger.info(f"✅ SVD applied: {self.tfidf_matrix.shape[1]} features")
            self.logger.info("Models loaded successfully!")
            
        except Exception as e:
            self.logger.error(f"Error loading models: {e}")
            raise
    
    def _create_combined_features(self) -> pd.Series:
        """Create combined features from available columns."""
        features_parts = []
        for col in ['overview', 'genres', 'keywords']:
            features_parts.append(self.movies_df[col].fillna('') if col in self.movies_df.columns else pd.Series([''] * len(self.movies_df)))
        combined = features_parts[0]
        for part in features_parts[1:]:
            combined = combined + ' ' + part
        return combined
    
    @lru_cache(maxsize=100)
    def search_movie_tmdb(self, movie_name: str) -> Optional[Dict]:
        """Search for a movie in TMDB API with caching."""
        if not self.tmdb_api_key:
            return None
        try:
            search_url = "https://api.themoviedb.org/3/search/movie"
            params = {'api_key': self.tmdb_api_key, 'query': movie_name, 'language': 'en-US', 'page': 1}
            response = requests.get(search_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data['results']:
                    movie = data['results'][0]
                    return self._get_tmdb_movie_details(movie['id'])
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"TMDB API request error: {e}")
            return None
    
    def _get_tmdb_movie_details(self, movie_id: int) -> Optional[Dict]:
        """Get detailed movie information from TMDB."""
        try:
            detail_url = f"https://api.themoviedb.org/3/movie/{movie_id}"
            detail_params = {'api_key': self.tmdb_api_key, 'language': 'en-US'}
            detail_response = requests.get(detail_url, params=detail_params, timeout=10)
            if detail_response.status_code == 200:
                detailed_movie = detail_response.json()
                genres = ' '.join([g['name'] for g in detailed_movie.get('genres', [])])
                return {
                    'title': detailed_movie.get('title', ''),
                    'overview': detailed_movie.get('overview', ''),
                    'genres': genres,
                    'release_date': detailed_movie.get('release_date', ''),
                    'vote_average': detailed_movie.get('vote_average', 0),
                    'poster_path': detailed_movie.get('poster_path', ''),
                    'tmdb_id': movie_id,
                    'source': 'TMDB'
                }
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"TMDB details API error: {e}")
            return None
    
    @lru_cache(maxsize=100)
    def search_movie_omdb(self, movie_name: str) -> Optional[Dict]:
        """Search for a movie in OMDB API as fallback with caching."""
        if not self.omdb_api_key:
            return None
        try:
            url = "http://www.omdbapi.com/"
            params = {'apikey': self.omdb_api_key, 't': movie_name, 'type': 'movie', 'plot': 'full'}
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('Response') == 'True':
                    return {
                        'title': data.get('Title', movie_name),
                        'overview': data.get('Plot', ''),
                        'genres': data.get('Genre', '').replace(', ', ' '),
                        'release_date': data.get('Year', ''),
                        'vote_average': self._parse_imdb_rating(data.get('imdbRating', '0')),
                        'poster_path': data.get('Poster', ''),
                        'imdb_id': data.get('imdbID', ''),
                        'source': 'OMDB'
                    }
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"OMDB API error: {e}")
            return None
    
    def _parse_imdb_rating(self, rating_str: str) -> float:
        try:
            return float(rating_str) if rating_str != 'N/A' else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def find_movie_in_dataset(self, movie_name: str) -> Optional[int]:
        """Check if movie exists in the dataset and return its index."""
        movie_name_lower = movie_name.lower().strip()
        exact_mask = self.movies_df['title'].str.lower().str.strip() == movie_name_lower
        if exact_mask.any():
            return self.movies_df[exact_mask].index[0]
        partial_mask = self.movies_df['title'].str.lower().str.contains(movie_name_lower, na=False, regex=False)
        if partial_mask.any():
            return self.movies_df[partial_mask].index[0]
        return None
    
    def recommend_for_existing_movie(self, movie_idx: int, n_recommendations: int = 10) -> List[Dict]:
        """Recommend movies for a movie in the dataset using only KMeans clusters and ratings."""
        if not hasattr(self, 'kmeans_model') or self.kmeans_model is None:
            self.logger.warning("KMeans model not available, falling back to popular movies")
            return self.get_popular_movies(n_recommendations)

        try:
            movie_cluster = self.kmeans_model.predict(self.tfidf_matrix[movie_idx:movie_idx+1])[0]
            cluster_movies = self.movies_df[self.kmeans_model.labels_ == movie_cluster].drop(
                self.movies_df.index[movie_idx], errors='ignore'
            )

            if 'vote_average' in cluster_movies.columns:
                top_movies = cluster_movies.nlargest(n_recommendations, 'vote_average')
            else:
                top_movies = cluster_movies.head(n_recommendations)

            recommendations = []
            for _, movie in top_movies.iterrows():
                recommendations.append({
                    'title': movie.get('title', 'Unknown'),
                    'overview': movie.get('overview', ''),
                    'genres': movie.get('genres', ''),
                    'release_date': movie.get('release_date', ''),
                    'vote_average': float(movie.get('vote_average', 0)),
                    'poster_path': movie.get('poster_path', ''),
                    'similarity_score': 0.0,
                    'recommendation_method': 'cluster_based'
                })
            return recommendations

        except Exception as e:
            self.logger.error(f"Cluster-based recommendation failed: {e}")
            return self.get_popular_movies(n_recommendations)
    
    def get_popular_movies(self, n_movies: int = 10) -> List[Dict]:
        """Get popular movies as fallback recommendations."""
        if 'vote_average' in self.movies_df.columns and 'vote_count' in self.movies_df.columns:
            popular_movies = self.movies_df.nlargest(n_movies * 2, 'vote_average')
            popular_movies = popular_movies.nlargest(n_movies, 'vote_count')
        elif 'vote_average' in self.movies_df.columns:
            popular_movies = self.movies_df.nlargest(n_movies, 'vote_average')
        else:
            popular_movies = self.movies_df.head(n_movies)
            
        recommendations = []
        for _, movie in popular_movies.iterrows():
            recommendations.append({
                'title': movie.get('title', 'Unknown'),
                'overview': movie.get('overview', ''),
                'genres': movie.get('genres', ''),
                'release_date': movie.get('release_date', ''),
                'vote_average': float(movie.get('vote_average', 0)),
                'poster_path': movie.get('poster_path', ''),
                'similarity_score': 0.0,
                'recommendation_method': 'popular'
            })
        return recommendations
    
    def get_recommendations(
        self,
        movie_name: str,
        n_recommendations: int = 10,
        preference_genres: Optional[List[str]] = None
    ) -> Dict:
        """Main method to get movie recommendations using clusters and ratings only."""
        preference_genres = preference_genres or []
        result = {'status': 'success', 'searched_movie': None, 'recommendations': [], 'message': ''}
        
        movie_idx = self.find_movie_in_dataset(movie_name)
        if movie_idx is not None:
            movie = self.movies_df.iloc[movie_idx]
            result['searched_movie'] = {
                'title': movie.get('title', movie_name),
                'overview': movie.get('overview', ''),
                'genres': movie.get('genres', ''),
                'release_date': movie.get('release_date', ''),
                'vote_average': float(movie.get('vote_average', 0)),
                'poster_path': movie.get('poster_path', ''),
                'source': 'dataset'
            }
            recs = self.recommend_for_existing_movie(movie_idx, n_recommendations * 2)
            result['message'] = 'Movie found in dataset'
        else:
            movie_info = self.search_movie_tmdb(movie_name) or self.search_movie_omdb(movie_name)
            if movie_info:
                result['searched_movie'] = movie_info
                recs = self.get_popular_movies(n_recommendations * 2)
                result['message'] = f'Movie found via {movie_info["source"]} API'
            else:
                result['status'] = 'not_found'
                result['message'] = f'Movie "{movie_name}" not found'
                recs = self.get_popular_movies(n_recommendations)

        if preference_genres:
            filtered_recs = [rec for rec in recs if any(
                genre.lower() in rec.get('genres', '').lower() for genre in preference_genres)]
            recs = filtered_recs if filtered_recs else recs

        result['recommendations'] = recs[:n_recommendations]
        return result


# Example usage
if __name__ == "__main__":
    os.environ['TMDB_API_KEY'] = 'your_tmdb_key'
    os.environ['OMDB_API_KEY'] = 'your_omdb_key'
    
    recommender = MovieRecommender(artifacts_path='artifacts/')
    test_movies = ["Inception", "The Matrix", "Some Unknown Movie 2024"]
    
    for movie in test_movies:
        print(f"\n{'='*50}")
        print(f"Searching for: {movie}")
        print('='*50)
        
        results = recommender.get_recommendations(movie, n_recommendations=5)
        print(f"Status: {results['status']}")
        print(f"Message: {results['message']}")
        
        if results['searched_movie']:
            print(f"\nSearched Movie Details:")
            print(f"  Title: {results['searched_movie']['title']}")
            print(f"  Source: {results['searched_movie'].get('source', 'N/A')}")
            print(f"  Genres: {results['searched_movie'].get('genres', 'N/A')}")
        
        print(f"\nTop 5 Recommendations:")
        for i, rec in enumerate(results['recommendations'], 1):
            print(f"  {i}. {rec['title']} (Rating: {rec['vote_average']:.1f}, Method: {rec['recommendation_method']})")
