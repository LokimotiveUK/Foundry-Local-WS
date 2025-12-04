"""
title: Job Search RAG
description: Search your resumes, cover letters, and job application documents
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
        self.category = "job-search"

    def search_job_documents(
        self,
        query: str,
    ) -> str:
        """
        Search your job search documents including resumes, CVs, cover letters, and job applications.

        Use this tool when the user:
        - Asks about their resume or CV
        - Wants feedback on cover letters
        - Needs help with job applications
        - Asks about their work experience or skills
        - Wants to improve their job application materials
        - Asks about ATS optimization

        :param query: The question about your job search documents
        :return: Answer based on your job search documents
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

            output = result.get("answer", "No relevant information found in your job search documents.")

            if result.get("sources"):
                output += "\n\n**Sources:**\n"
                for source in result["sources"]:
                    output += f"- {source['document']} (relevance: {source.get('relevance', 'N/A')})\n"

            return output

        except requests.exceptions.ConnectionError:
            return "Error: Cannot connect to RAG server. Make sure the private-rag containers are running (docker compose up -d)."
        except requests.exceptions.Timeout:
            return "Error: Request timed out. The RAG server may be busy."
        except Exception as e:
            return f"Error searching documents: {str(e)}"

    def get_resume_summary(self, __user__: dict = {}) -> str:
        """
        Get a summary of your resume/CV on file.

        Use this when the user asks for an overview of their resume or wants to know what's in their CV.

        :return: Summary of your resume
        """
        return self.search_job_documents("Summarize my resume including key skills, experience, and qualifications")

    def suggest_resume_improvements(
        self,
        job_title: str,
    ) -> str:
        """
        Get suggestions to improve your resume for a specific job title.

        Use this when the user wants to tailor their resume for a specific role.

        :param job_title: The job title to optimize the resume for
        :return: Suggestions for improving the resume
        """
        query = f"Based on my resume, suggest specific improvements to make it more suitable for a {job_title} position. Focus on ATS optimization, keyword improvements, and highlighting relevant experience."
        return self.search_job_documents(query)
