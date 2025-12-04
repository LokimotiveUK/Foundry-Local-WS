"""
title: Finance RAG
description: Search your financial documents including bank statements, tax returns, and investment reports
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
        self.category = "finance"

    def search_finance_documents(
        self,
        query: str,
    ) -> str:
        """
        Search your financial documents including bank statements, tax returns, investment reports, and receipts.

        Use this tool when the user:
        - Asks about their income or expenses
        - Wants to know about tax information
        - Asks about investments or portfolio
        - Needs information from bank statements
        - Wants to understand their financial history
        - Asks about specific transactions or payments

        IMPORTANT: This tool only retrieves and summarizes information from documents.
        It does NOT provide financial advice. Always recommend consulting a financial advisor for major decisions.

        :param query: The question about your financial documents
        :return: Information from your financial documents
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

            output = result.get("answer", "No relevant information found in your financial documents.")

            if result.get("sources"):
                output += "\n\n**Sources:**\n"
                for source in result["sources"]:
                    output += f"- {source['document']} (relevance: {source.get('relevance', 'N/A')})\n"

            output += "\n\n*Note: This is a summary of your documents, not financial advice. Consult a financial advisor for major financial decisions.*"

            return output

        except requests.exceptions.ConnectionError:
            return "Error: Cannot connect to RAG server. Make sure the private-rag containers are running (docker compose up -d)."
        except requests.exceptions.Timeout:
            return "Error: Request timed out. The RAG server may be busy."
        except Exception as e:
            return f"Error searching documents: {str(e)}"

    def get_income_summary(self, __user__: dict = {}) -> str:
        """
        Get a summary of your income from your documents.

        Use this when the user asks about their income, salary, or earnings.

        :return: Summary of income information
        """
        return self.search_finance_documents("What is my total income? Include salary, wages, and any other income sources with amounts and dates.")

    def get_tax_summary(self, __user__: dict = {}) -> str:
        """
        Get a summary of your tax information.

        Use this when the user asks about taxes, deductions, or tax returns.

        :return: Summary of tax information
        """
        return self.search_finance_documents("Summarize my tax information including total income, deductions claimed, taxes paid, and refunds.")

    def list_major_expenses(self, __user__: dict = {}) -> str:
        """
        List major expenses from your financial documents.

        Use this when the user asks about their spending or expenses.

        :return: List of major expenses
        """
        return self.search_finance_documents("What are my major expenses? List significant payments, purchases, or recurring expenses with amounts.")

    def get_investment_summary(self, __user__: dict = {}) -> str:
        """
        Get a summary of your investments.

        Use this when the user asks about their investment portfolio or assets.

        :return: Summary of investments
        """
        return self.search_finance_documents("Summarize my investments including stocks, bonds, retirement accounts, and other assets with current values if available.")
