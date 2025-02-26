import os
# Set environment variable to disable watchdog for PyTorch
os.environ["STREAMLIT_WATCH_FORCE_POLLING"] = "true"

import streamlit as st
from llama_index.core import (
    VectorStoreIndex, 
    Settings,
    SimpleDirectoryReader
)
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import tempfile
from dotenv import load_dotenv
from pygments.lexers import get_lexer_for_filename

# Set page configuration
st.set_page_config(page_title="Chat with Documents", layout="wide")

# Initialize session state variables
if "messages" not in st.session_state:
    st.session_state.messages = []
if "index" not in st.session_state:
    st.session_state.index = None
if "processed_file" not in st.session_state:
    st.session_state.processed_file = False

# Load environment variables
load_dotenv()

# Configure Ollama with proper parameters
Settings.llm = Ollama(
    model="pawan941394/HindAI:latest",  # Change this to your preferred model
    request_timeout=120.0,
    temperature=0.1,
    context_window=3900,
    base_url="https://sunny-gerri-finsocialdigitalsystem-d9b385fa.koyeb.app", 
    additional_kwargs={
        "seed": 42,  # for reproducibility
        "num_predict": 128,  # max tokens to generate
        "top_k": 20,
        "top_p": 0.9,
        "mirostat_mode": 2,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
    }
)

# Use HuggingFace embedding model with specific parameters
Settings.embed_model = HuggingFaceEmbedding(
    model_name="sentence-transformers/all-mpnet-base-v2",
    embed_batch_size=100
)

# Configure chunk settings with optimized values
Settings.chunk_size = 512  # Smaller chunks for better context
Settings.chunk_overlap = 50

def get_file_extension(filename):
    return os.path.splitext(filename)[1].lower()

def is_code_file(filename):
    code_extensions = {
        '.py', '.js', '.java', '.cpp', '.c', '.cs', '.html', '.css', 
        '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.ts', '.sql',
        '.xml', '.json', '.yaml', '.yml', '.sh', '.bat', '.ps1'
    }
    return get_file_extension(filename) in code_extensions

def display_message_content(message):
    content = message["content"]
    if message.get("is_code"):
        st.code(content, language=message.get("language", "python"))
    else:
        st.write(content)

def process_file(uploaded_file):
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save uploaded file
            file_path = os.path.join(temp_dir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            
            # Create document reader with better error handling
            reader = SimpleDirectoryReader(
                input_dir=temp_dir,
                filename_as_id=True,
                recursive=False
            )
            documents = reader.load_data()
            
            # Add metadata about file type
            for doc in documents:
                if is_code_file(uploaded_file.name):
                    try:
                        lexer = get_lexer_for_filename(uploaded_file.name)
                        doc.metadata["is_code"] = True
                        doc.metadata["language"] = lexer.aliases[0]
                    except:
                        doc.metadata["is_code"] = False
            
            # Create index using Settings instead of service_context
            index = VectorStoreIndex.from_documents(
                documents,
                show_progress=True
            )
            return index
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return None

def main():
    st.title("Chat with Documents")
    
    # Updated file upload section with all LlamaIndex supported types
    uploaded_file = st.file_uploader(
        "Upload your document", 
        type=[
            # Documents
            "pdf", "docx", "doc", "txt", "rtf", "odt", 
            # Markdown & Documentation
            "md", "rst", "tex",
            # Emails
            "eml", "msg", "mbox", "pst",
            # Presentations
            "pptx", "ppt", "odp",
            # Spreadsheets
            "xlsx", "xls", "csv", "ods", "numbers",
            # Audio & Video
            "mp3", "mp4", "mpeg", "wav", "webm",
            # Code & Data files
            "py", "js", "java", "cpp", "c", "cs", "html", 
            "css", "php", "rb", "go", "rs", "swift", "kt", "ts",
            "json", "xml", "yaml", "yml", "toml", "ini",
            # E-books & Documents
            "epub", "mobi", "chm",
            # Archives
            "zip", "tar", "gz", "7z", "rar",
            # Web & Communication
            "html", "htm", "mht", "mhtml",
            # Database
            "sqlite", "db",
            # Others
            "ipynb", "key"
        ]
    )

    # Process button with state tracking
    if uploaded_file and st.button("Process Document"):
        with st.spinner("Processing document..."):
            index = process_file(uploaded_file)
            if index:
                st.session_state.index = index
                st.session_state.processed_file = True
                st.success("Document processed successfully!")

    # Chat interface with explicit state checks
    if st.session_state.get("processed_file", False) and st.session_state.get("index") is not None:
        # Display chat messages with syntax highlighting
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                display_message_content(message)

        # Chat input
        query = st.chat_input("Ask a question about your document:")
        if query:
            try:
                # Add user message to chat history
                st.session_state.messages.append({"role": "user", "content": query})
                
                # Configure query engine with streaming
                query_engine = st.session_state.index.as_query_engine(
                    streaming=True,
                    similarity_top_k=3
                )
                
                # Process query with error handling
                with st.spinner("Thinking..."):
                    response = query_engine.query(query)
                    # Handle streaming response
                    response_text = ""
                    is_streaming = hasattr(response, 'response_gen')
                    
                    if is_streaming:
                        response_placeholder = st.empty()
                        for text in response.response_gen:
                            response_text += text
                            response_placeholder.markdown(response_text + "▌")
                        response_placeholder.markdown(response_text)
                    else:
                        response_text = str(response)
                
                # Check if the response contains code
                is_code = any(doc.metadata.get("is_code", False) for doc in response.source_nodes)
                message_data = {
                    "role": "assistant",
                    "content": response_text,
                    "is_code": is_code
                }
                if is_code:
                    message_data["language"] = response.source_nodes[0].metadata.get("language", "python")
                st.session_state.messages.append(message_data)
                # Force streamlit to rerun to display new messages
                st.rerun()
            except Exception as e:
                st.error(f"Error processing query: {str(e)}")

if __name__ == "__main__":
    main()
