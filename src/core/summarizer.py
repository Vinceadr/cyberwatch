"""Summarizer — synthese et classification via Ollama LLM local (traduction supprimee)."""

import logging

import ollama as ollama_client

logger = logging.getLogger(__name__)

TECHNICAL_TERMS_NOTICE = (
    "Conserve les termes techniques en anglais quand c'est l'usage courant "
    "(CVE, RCE, zero-day, buffer overflow, XSS, SQL injection, LLM, GPU, "
    "API, SDK, framework, runtime, backdoor, ransomware, phishing, exploit, "
    "patch, firmware, kernel, container, cluster, endpoint, etc.)."
)


class Summarizer:
    def __init__(self, config: dict) -> None:
        self.llm_config = config.get("llm", {})
        self.model = self.llm_config.get("model", "llama3.1:8b")
        self.fallback_model = self.llm_config.get("fallback_model", "mistral:7b")
        self.base_url = self.llm_config.get("base_url", "http://localhost:11434")
        self.timeout = self.llm_config.get("timeout_seconds", 120)
        self.tasks = self.llm_config.get("tasks", {})
        self._client = ollama_client.Client(host=self.base_url, timeout=self.timeout)

    def summarize(self, text: str) -> str:
        task_config = self.tasks.get("summarize", {})
        system_prompt = task_config.get(
            "system_prompt",
            f"Tu es un analyste en veille technologique. Resume cet article en 2-3 phrases "
            f"concises en francais. Identifie le sujet principal, l'impact et les actions "
            f"recommandees si applicable. {TECHNICAL_TERMS_NOTICE}",
        )
        return self._query(system_prompt, text[:3000])

    def classify(self, text: str) -> str:
        task_config = self.tasks.get("classify", {})
        system_prompt = task_config.get(
            "system_prompt",
            "Classe cette information selon son niveau d'importance et d'urgence: "
            "CRITIQUE, HAUTE, MOYENNE, BASSE, INFO. "
            "Reponds UNIQUEMENT par le niveau, rien d'autre.",
        )
        result = self._query(system_prompt, text[:2000])
        severity = result.strip().upper().split()[0] if result.strip() else "INFO"
        valid = {"CRITIQUE", "HAUTE", "MOYENNE", "BASSE", "INFO"}
        return severity if severity in valid else "INFO"

    def _query(self, system_prompt: str, user_content: str) -> str:
        try:
            response = self._client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            )
            return response["message"]["content"]
        except Exception:
            logger.warning("Modele %s indisponible, fallback %s", self.model, self.fallback_model)
            try:
                response = self._client.chat(
                    model=self.fallback_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                )
                return response["message"]["content"]
            except Exception:
                logger.exception("LLM indisponible (model + fallback)")
                return ""

    def is_available(self) -> bool:
        try:
            self._client.list()
            return True
        except Exception:
            return False