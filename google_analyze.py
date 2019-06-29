"""Analyzes text using the Google Cloud Natural Language API."""

from typing import List
import googleapiclient.discovery
from googleapiclient.errors import HttpError

def extract_entities(text: str, encoding: str = 'UTF32') -> List[str]:
    try:
        body = {
            'document': {
                'type': 'PLAIN_TEXT',
                'content': text,
            },
            'encoding_type': encoding,
        }
        service = googleapiclient.discovery.build('language', 'v1')
        request = service.documents().analyzeEntities(body=body)
        response = request.execute()
    except HttpError:
        return []
    return [
        entity['name']
        for entity in response['entities']
        if entity['type'] == "PERSON"
    ]
