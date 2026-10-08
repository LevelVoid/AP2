"""
HIVE Dual-Layer Interceptor Module.
Provides deterministic (math) and semantic (vector) checks to intercept
and authorize transactions.
"""
import re
import math
from typing import Dict, Any, Optional

try:
    from sentence_transformers import SentenceTransformer
    from sentence_transformers.util import cos_sim
except ImportError:
    SentenceTransformer = None

class HIVEInterceptor:
    """
    Middleware class to intercept PaymentMandate payloads before they are cryptographically signed.
    Enforces rules to prevent Confused Deputy Attacks and prompt injection scenarios.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", threshold: float = 0.75):
        """
        Initializes the HIVEInterceptor with a local SentenceTransformer model.

        Args:
            model_name (str): Name of the HuggingFace sentence-transformers model.
            threshold (float): Similarity threshold used for Layer 2 Semantic Verification.
        """
        self.threshold = threshold
        if SentenceTransformer is not None:
            self.model = SentenceTransformer(model_name)
        else:
            self.model = None

    def _evaluate_layer_1(self, mandate_max_amount: float, mandate_currency: str, amount: float, currency: str) -> Optional[Dict[str, Any]]:
        """
        Phase 1: Layer 1 (Scalar & Categorical Verification).
        Mathematically blocks transactions if the agent was coerced into inflating
        prices beyond the user's authorized limit or changing the currency.

        Args:
            mandate_max_amount (float): The maximum amount authorized by the user.
            mandate_currency (str): The requested currency format.
            amount (float): The candidate transaction amount.
            currency (str): The candidate transaction currency.

        Returns:
            Optional[Dict]: A failure result payload if Layer 1 fails, else None.
        """
        if amount > mandate_max_amount:
            return {
                "is_authorized": False,
                "layer_failed": 1,
                "reason": f"Amount {amount} exceeds max amount {mandate_max_amount}",
                "similarity_score": None
            }

        if currency != mandate_currency:
            return {
                "is_authorized": False,
                "layer_failed": 1,
                "reason": f"Currency {currency} does not match {mandate_currency}",
                "similarity_score": None
            }
        
        return None

    def _evaluate_layer_2(self, user_intent_string: str, item_description: str) -> Optional[Dict[str, Any]]:
        """
        Phase 2: Layer 2 (Semantic Vector Verification).
        Utilizes local dense vector embeddings to block transactions if the agent
        substitutes the user's requested item for a malicious asset, while preserving 
        utility by allowing benign synonyms.

        Args:
            user_intent_string (str): Original task prompt describing the intent.
            item_description (str): Description of the actual item in the checkout cart.

        Returns:
            Optional[Dict]: A failure/success result payload containing the similarity score.
        """
        if self.model is None:
            return {
                "is_authorized": False,
                "layer_failed": 2,
                "reason": "SentenceTransformer model not available",
                "similarity_score": None
            }

        try:
            tensor_a = self.model.encode(user_intent_string, convert_to_tensor=True)
            tensor_b = self.model.encode(item_description, convert_to_tensor=True)
            
            similarity = float(cos_sim(tensor_a, tensor_b)[0][0])
            
            if similarity < self.threshold:
                return {
                    "is_authorized": False,
                    "layer_failed": 2,
                    "reason": f"Semantic similarity {similarity:.2f} is below threshold {self.threshold}",
                    "similarity_score": similarity
                }
            
            # Since Layer 2 requires score output, we should return the successful score if it passes
            return {
                "is_authorized": True,
                "layer_failed": None,
                "reason": "Verification passed",
                "similarity_score": similarity
            }
        except Exception as e:
            return {
                "is_authorized": False,
                "layer_failed": 2,
                "reason": f"Error computing semantic similarity: {str(e)}",
                "similarity_score": None
            }

    def verify_transaction(self, user_intent_string: str, mandate_max_amount: float, mandate_currency: str, candidate_payload: dict) -> Dict[str, Any]:
        """
        Executes the dual-layer pipeline (Layer 1 Math Constraints -> Layer 2 Semantic Check)
        to verify if the generated candidate payment payload is safe to authorize.

        Args:
            user_intent_string (str): User's original prompt (e.g. from agent state).
            mandate_max_amount (float): Parsed numeric budget constraint.
            mandate_currency (str): Mandate base currency (e.g. USD).
            candidate_payload (dict): Requires 'amount', 'currency', and 'item_description'.

        Returns:
            Dict: Result payload stating authorization status, failure reason (if any), 
                  and semantic similarity scoring.
        """
        amount = candidate_payload.get("amount")
        currency = candidate_payload.get("currency")
        item_description = candidate_payload.get("item_description")

        if amount is None or currency is None or item_description is None:
            return {
                "is_authorized": False,
                "layer_failed": 1,
                "reason": "Missing required fields in candidate payload",
                "similarity_score": None
            }
            
        try:
            amount_float = float(amount)
        except ValueError:
            return {
                "is_authorized": False,
                "layer_failed": 1,
                "reason": f"Amount '{amount}' cannot be converted to float",
                "similarity_score": None
            }

        # 1. Execute Phase 1: Layer 1
        layer_1_result = self._evaluate_layer_1(mandate_max_amount, mandate_currency, amount_float, currency)
        if layer_1_result is not None:
            return layer_1_result
            
        # 2. Execute Phase 2: Layer 2
        layer_2_result = self._evaluate_layer_2(user_intent_string, item_description)
        if layer_2_result is not None and layer_2_result.get("is_authorized") is False:
            return layer_2_result
            
        # 3. Success Fallback
        return layer_2_result if layer_2_result is not None else {
            "is_authorized": True,
            "layer_failed": None,
            "reason": "Verification passed",
            "similarity_score": None
        }
