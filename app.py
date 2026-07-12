import streamlit as st
import requests
import time

st.set_page_config(
    page_title="Flair | Démo",
    page_icon="🔮",
    layout="centered"
)

st.title("Flair - Détection de Fraude")
st.markdown("Testez notre endpoint `POST /v1/analyze` en envoyant un document.")
st.divider()

st.markdown("### 📄 Soumettre un document")
uploaded_file = st.file_uploader("Uploadez le fichier à analyser", type=["pdf", "png", "jpg", "jpeg", "csv", "txt"])

if uploaded_file is not None:
    if st.button("Lancer l'analyse Flair", use_container_width=True, type="primary"):
        with st.spinner("Analyse du document en cours..."):
            API_URL = "https://api.myflair.app/v1/analyze" 
            HEADERS = {
                "X-API-Key": "TON_API_KEY_ICI" 
                # Attention: Ne pas forcer le Content-Type ici, 'requests' 
                # le gérera automatiquement avec le bon boundary pour le multipart.
            }
            
            try:
                # ==========================================
                # 🔌 VRAI APPEL API (Décommente pour l'activer)
                # ==========================================
                # files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                # response = requests.post(API_URL, headers=HEADERS, files=files)
                # response.raise_for_status()
                # data = response.json()
                
                # ==========================================
                # 🧪 SIMULATION BASÉE SUR TA DOC (À supprimer)
                # ==========================================
                time.sleep(1.2)
                data = {
                    "dossier_id": "dos_8f73b2a9e",
                    "document": {
                        "document_id": "doc_9a8b7c6d5",
                        "filename": uploaded_file.name,
                        "content_hash": "a1b2c3d4e5f6g7h8i9j0",
                        "deduplicated": False,
                        "status": "completed",
                        "verdict": "fraud", # ou "legit"
                        "is_recaptured": False,
                        "used_external_api": True,
                        "duration_ms": 1450,
                        "credits_used": 1,
                        "layers": [
                            {"layer_name": "metadata_check", "flagged": True},
                            {"layer_name": "pixel_analysis", "flagged": False}
                        ]
                    },
                    "debug": {}
                }

                doc_info = data.get("document", {})
                verdict = doc_info.get("verdict", "unknown").upper()
                
                if verdict == "FRAUD":
                    st.error("🚨 ALERTE FRAUDE DÉTECTÉE", icon="🚨")
                elif verdict == "LEGIT":
                    st.success("✅ DOCUMENT LÉGITIME", icon="✅")
                else:
                    st.warning(f"⚠️ VERDICT : {verdict}")
                
                st.markdown("### 📊 Détails de l'analyse")
                col1, col2, col3, col4 = st.columns(4)
                
                col1.metric("Statut", doc_info.get("status", "N/A").capitalize())
                col2.metric("Temps de réponse", f"{doc_info.get('duration_ms', 0)} ms")
                col3.metric("Crédits", doc_info.get("credits_used", 0))
                col4.metric("Dédupliqué", "Oui" if doc_info.get("deduplicated") else "Non")
                
                st.divider()
                
                st.markdown(f"**Dossier ID :** `{data.get('dossier_id')}`")
                st.markdown(f"**Document ID :** `{doc_info.get('document_id')}`")
                
                if doc_info.get("layers"):
                    st.markdown("#### 🔍 Couches d'analyse (Layers) :")
                    for layer in doc_info.get("layers"):
                        status_icon = "🛑" if layer.get("flagged") else "🟢"
                        st.markdown(f"- {status_icon} **{layer.get('layer_name')}**")
                
                with st.expander("👨‍💻 Voir la réponse JSON brute"):
                    st.json(data)
                    
            except Exception as e:
                st.error(f"Erreur lors de la communication avec l'API : {e}")
