"""
Open WebUI Tool: Private Document Search

Copy this code into Open WebUI:
1. Go to Workspace > Tools
2. Click "+ Create Tool"
3. Paste this code
4. Save and enable the tool

This tool connects to the local RAG server to search your private documents.
"""

import json
from typing import Optional
import requests


class Tools:
    def __init__(self):
        self.rag_server = "http://localhost:8000"

    def search_private_docs(
        self,
        query: str,
        category: Optional[str] = None,
        __user__: dict = {},
    ) -> str:
        """
        Search your private healthcare and finance documents.

        Use this tool when the user asks about their personal documents,
        medical records, lab results, financial statements, tax returns, etc.

        :param query: The search query or question about your documents
        :param category: Optional filter - 'healthcare' or 'finance'
        :return: Relevant information from your private documents
        """
        try:
            response = requests.post(
                f"{self.rag_server}/query",
                json={
                    "query": query,
                    "category": category,
                    "top_k": 5,
                    "include_sources": True
                },
                timeout=60
            )
            response.raise_for_status()
            result = response.json()

            # Format the response
            output = f"**Answer:**\n{result['answer']}\n\n"

            if result.get('sources'):
                output += "**Sources:**\n"
                for i, source in enumerate(result['sources'], 1):
                    output += f"{i}. {source['document']} (relevance: {source['relevance']})\n"

            return output

        except requests.exceptions.ConnectionError:
            return "Error: RAG server not running. Start it with: python rag_server.py"
        except Exception as e:
            return f"Error searching documents: {str(e)}"

    def search_healthcare_docs(
        self,
        query: str,
        __user__: dict = {},
    ) -> str:
        """
        Search your healthcare documents (medical records, lab results, prescriptions).

        :param query: Your question about healthcare documents
        :return: Information from your healthcare documents
        """
        return self.search_private_docs(query, category="healthcare")

    def search_finance_docs(
        self,
        query: str,
        __user__: dict = {},
    ) -> str:
        """
        Search your financial documents (bank statements, tax returns, investments).

        :param query: Your question about financial documents
        :return: Information from your financial documents
        """
        return self.search_private_docs(query, category="finance")
