import os, sys, time, logging

BASE = '/mnt/d/RAG工单/RAG工单7'
os.chdir(BASE)
sys.path.insert(0, BASE)
os.environ.setdefault('DEEPSEEK_API_KEY', 'sk-171c1cdaa57347628ee2f4ef8de4875c')

# Log everything to a file
logfile = '/tmp/server_debug.log'
logging.basicConfig(filename=logfile, level=logging.DEBUG, 
                    format='%(asctime)s %(levelname)s %(message)s')
logging.info('Starting server...')

# Test fastembed import
logging.info('Importing fastembed...')
from fastembed import TextEmbedding
logging.info('fastembed imported')

# Pre-load the embedding model
logging.info('Loading embedding model...')
embed_fn = TextEmbedding(model_name="BAAI/bge-small-zh-v1.5", max_length=512)
logging.info('Embedding model loaded')

# Now import the app
logging.info('Importing app_v7...')
from app_v7 import app
logging.info('App imported')

# Start uvicorn
import uvicorn
PORT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8507
logging.info(f'Starting uvicorn on port {PORT}...')
uvicorn.run(app, host='0.0.0.0', port=PORT, log_level='info')
