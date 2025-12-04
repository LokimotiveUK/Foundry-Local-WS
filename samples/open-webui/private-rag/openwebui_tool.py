"""
Open WebUI Tool: Private Document Search

Copy this code into Open WebUI:
1. Go to Workspace > Tools
2. Click "+ Create Tool"
3. Paste this code
4. Save and enable the tool

This tool connects to the local RAG server to search your private documents.

NOTE: Open WebUI runs in Docker, so use host.docker.internal to reach localhost.
"""

import json
from typing import Optional
import requests


class Tools:
    def __init__(self):
        # Use host.docker.internal since Open WebUI runs in Docker
        # This reaches the RAG server running on the host at port 8000
        self.rag_server = "http://host.docker.internal:8000"

    def search_private_docs(
        self,
        query: str,
        category: Optional[str] = None,
        __user__: dict = {},
    ) -> str:
        """
        Search your private documents (healthcare, finance, job-search, etc).

        Use this tool when the user asks about their personal documents,
        medical records, lab results, financial statements, resumes, cover letters, etc.

        :param query: The search query or question about your documents
        :param category: Optional filter - 'healthcare', 'finance', 'job-search', or any custom category
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
            return "Error: Cannot connect to RAG server at port 8000. Make sure the private-rag containers are running."
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

    def search_job_docs(
        self,
        query: str,
        __user__: dict = {},
    ) -> str:
        """
        Search your job search documents (resumes, cover letters, job applications).

        Use this when the user asks about their resume, CV, cover letters,
        or wants help improving job application materials.

        :param query: Your question about job search documents
        :return: Information from your job search documents
        """
        return self.search_private_docs(query, category="job-search")
