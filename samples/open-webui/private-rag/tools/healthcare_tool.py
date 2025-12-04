"""
title: Healthcare RAG
description: Search your medical records, lab results, prescriptions, and health documents
author: local
version: 1.0.0
required_open_webui_version: 0.4.0
requirements: requests
"""

import requests
from pydantic import BaseModel, Field
from typing import Optional


class Tools:
    class Valves(BaseModel):
        rag_server_url: str = Field(
            default="http://host.docker.internal:8000",
            description="URL of the RAG server"
        )

    def __init__(self):
        self.valves = self.Valves()
        self.category = "healthcare"

    def search_health_documents(
        self,
        query: str,
    ) -> str:
        """
        Search your healthcare documents including medical records, lab results, prescriptions, and doctor notes.

        Use this tool when the user:
        - Asks about their medical history
        - Wants to know about lab results or test values
        - Asks about prescriptions or medications
        - Needs information from doctor visits
        - Asks about diagnoses or health conditions
        - Wants to understand their health records

        IMPORTANT: This tool only retrieves and summarizes information from documents.
        It does NOT provide medical advice. Always recommend consulting a healthcare provider.

        :param query: The question about your health documents
        :return: Information from your healthcare documents
        """
        try:
            response = requests.post(
                f"{self.valves.rag_server_url}/query",
                json={
                    "query": query,
                    "category": self.category,
                    "top_k": 5,
                    "include_sources": True
                },
                timeout=60
            )
            response.raise_for_status()
            result = response.json()

            output = result.get("answer", "No relevant information found in your healthcare documents.")

            if result.get("sources"):
                output += "\n\n**Sources:**\n"
                for source in result["sources"]:
                    output += f"- {source['document']} (relevance: {source.get('relevance', 'N/A')})\n"

            output += "\n\n*Note: This is a summary of your documents, not medical advice. Consult a healthcare provider for medical decisions.*"

            return output

        except requests.exceptions.ConnectionError:
            return "Error: Cannot connect to RAG server. Make sure the private-rag containers are running (docker compose up -d)."
        except requests.exceptions.Timeout:
            return "Error: Request timed out. The RAG server may be busy."
        except Exception as e:
            return f"Error searching documents: {str(e)}"

    def get_recent_lab_results(self, __user__: dict = {}) -> str:
        """
        Get a summary of your recent lab results.

        Use this when the user asks about their lab work, blood tests, or test results.

        :return: Summary of recent lab results
        """
        return self.search_health_documents("What are my most recent lab results? Include specific values and dates.")

    def list_medications(self, __user__: dict = {}) -> str:
        """
        List your current medications and prescriptions.

        Use this when the user asks about their medications, prescriptions, or what drugs they're taking.

        :return: List of medications from your documents
        """
        return self.search_health_documents("List all my current medications, prescriptions, dosages, and instructions.")

    def summarize_health_history(self, __user__: dict = {}) -> str:
        """
        Get a summary of your health history from your documents.

        Use this when the user wants an overview of their medical history.

        :return: Summary of health history
        """
        return self.search_health_documents("Summarize my health history including major diagnoses, conditions, surgeries, and important health events.")
