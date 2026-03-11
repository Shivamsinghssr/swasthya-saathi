"""
agent/tools.py

5 tools for Swasthya Saathi agent.
Each tool is backed by hybrid RAG retrieval (BM25 + FAISS).
Tools are initialized at server startup via init_tools().
"""
from langchain_core.tools import tool
from typing import Optional

# Global retriever references — set once at startup
_symptom_retriever  = None
_medicine_retriever = None
_scheme_retriever   = None
_health_centers     = None


def init_tools(
    symptom_retriever,
    medicine_retriever,
    scheme_retriever,
    health_centers: list,
):
    """Called once at FastAPI startup to inject RAG retrievers."""
    global _symptom_retriever, _medicine_retriever, _scheme_retriever, _health_centers
    _symptom_retriever  = symptom_retriever
    _medicine_retriever = medicine_retriever
    _scheme_retriever   = scheme_retriever
    _health_centers     = health_centers
    print("[Tools] All tools initialized ✅")


# ── Tool 1: Symptom Checker ───────────────────────────────────────────────────

@tool
def symptom_checker(symptoms: str) -> str:
    """
    Check symptoms and return relevant health information in Hindi.
    
    Use this tool when the user describes physical symptoms like:
    fever (bukhar), cough (khansi), stomach pain (pet dard), weakness (kamzori),
    vomiting (ulti), diarrhea (dast), headache (sar dard), etc.
    
    Args:
        symptoms: Description of symptoms in Hindi or English
        
    Returns:
        Health information about possible conditions and recommended actions
    """
    if not _symptom_retriever:
        return "Error: Symptom checker not initialized."

    results = _symptom_retriever.retrieve(symptoms, top_k=3)
    if not results:
        return (
            "Is lakshan ke baare mein database mein jaankari nahi mili. "
            "Kripya nazdeeki PHC ya doctor se milein."
        )

    context_parts = []
    for chunk, score in results:
        context_parts.append(chunk.text)

    return "=== SYMPTOM KNOWLEDGE BASE ===\n\n" + "\n\n---\n\n".join(context_parts)


# ── Tool 2: Medicine Explainer ────────────────────────────────────────────────

@tool
def medicine_explainer(medicine_name: str) -> str:
    """
    Explain a medicine in simple Hindi: what it treats, how to take it, side effects.
    
    Use this tool when user asks about a specific medicine like:
    Paracetamol, Crocin, ORS, Amoxicillin, Metformin, iron tablets, etc.
    Works with both brand names (Crocin) and generic names (Paracetamol).
    
    Args:
        medicine_name: Name of the medicine (brand or generic)
        
    Returns:
        Plain Hindi explanation of the medicine
    """
    if not _medicine_retriever:
        return "Error: Medicine database not initialized."

    results = _medicine_retriever.retrieve(medicine_name, top_k=3)
    if not results:
        return (
            f"'{medicine_name}' ke baare mein database mein jaankari nahi mili. "
            "Kripya apne doctor ya pharmacist se poochein."
        )

    context_parts = []
    for chunk, score in results:
        context_parts.append(chunk.text)

    return "=== MEDICINE KNOWLEDGE BASE ===\n\n" + "\n\n---\n\n".join(context_parts)


# ── Tool 3: Scheme Checker ────────────────────────────────────────────────────

@tool
def scheme_checker(query: str) -> str:
    """
    Find government health schemes available in UP and Bihar.
    
    Use this tool when user asks about:
    - Free treatment (muft ilaaj)
    - Government hospitals (sarkari aspatal)
    - Ayushman Bharat / PMJAY health card
    - Janani Suraksha Yojana (for pregnant women)
    - Any state or central health scheme
    
    Args:
        query: User's question about health schemes or their eligibility
        
    Returns:
        Information about relevant government health schemes
    """
    if not _scheme_retriever:
        return "Error: Scheme database not initialized."

    results = _scheme_retriever.retrieve(query, top_k=3)
    if not results:
        return (
            "Is yojana ke baare mein jaankari nahi mili. "
            "Kripya apne gram pradhan, ASHA worker, ya block office se sampark karein."
        )

    context_parts = []
    for chunk, score in results:
        context_parts.append(chunk.text)

    return "=== GOVERNMENT SCHEMES ===\n\n" + "\n\n---\n\n".join(context_parts)


# ── Tool 4: Health Center Locator ─────────────────────────────────────────────

@tool
def health_center_locator(district: str) -> str:
    """
    Find nearest government health centers (PHC/CHC/District Hospital) in UP or Bihar.
    
    Use this tool when user asks about:
    - Nearest hospital (nazdeeki aspatal)
    - Government doctor (sarkari doctor)
    - PHC, CHC, or community health center
    - Where to go for treatment in their area
    
    Args:
        district: Name of the district in UP or Bihar
        
    Returns:
        List of nearby government health facilities with address and timings
    """
    if not _health_centers:
        return "Error: Health center data not loaded."

    district_lower = district.lower().strip()
    matches        = []

    for center in _health_centers:
        center_district = center.get("district", "").lower()
        if district_lower in center_district or center_district in district_lower:
            matches.append(center)

    if not matches:
        return (
            f"'{district}' ke liye health center data abhi available nahi hai. "
            "Apne gram pradhan ya ASHA worker se nazdeeki PHC ka pata poochein. "
            "Ya 104 (health helpline) par call karein — yeh free hai."
        )

    lines = [f"📍 {district.title()} mein government health centers:\n"]
    for center in matches[:5]:
        lines.append(f"🏥 {center['name']}")
        lines.append(f"   Prakar: {center['type']}")
        lines.append(f"   Pata: {center['address']}")
        lines.append(f"   Samay: {center.get('timing', 'Subah 8 baje se Shaam 4 baje')}")
        if center.get("phone"):
            lines.append(f"   Phone: {center['phone']}")
        lines.append("")

    lines.append("💡 Emergency mein 108 (free ambulance) call karein.")
    return "\n".join(lines)


# ── Tool 5: Prescription Reader ───────────────────────────────────────────────

@tool
def prescription_reader(medicine_names: str) -> str:
    """
    Read a full prescription with multiple medicines and explain each one in simple Hindi.
    
    Use this tool when user has a prescription slip with multiple medicines and
    wants to understand what each medicine is for.
    
    Args:
        medicine_names: Comma-separated list of medicine names from the prescription
                        Example: "Paracetamol, Amoxicillin, ORS, Zinc"
        
    Returns:
        Plain Hindi explanation of each medicine in the prescription
    """
    medicines = [m.strip() for m in medicine_names.split(",") if m.strip()]
    if not medicines:
        return "Koi dawa ka naam nahi mila. Kripya dawa ke naam comma se alag karke likhein."

    explanations = []
    for med in medicines:
        result = medicine_explainer.invoke({"medicine_name": med})
        explanations.append(f"💊 {med.upper()}:\n{result}")

    header = f"Aapki prescription mein {len(medicines)} dawayein hain:\n\n"
    return header + "\n\n" + ("=" * 40 + "\n\n").join(explanations)


# ── Tool list (imported by graph.py) ──────────────────────────────────────────

ALL_TOOLS = [
    symptom_checker,
    medicine_explainer,
    scheme_checker,
    health_center_locator,
    prescription_reader,
]
