import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import FewShotPromptTemplate, PromptTemplate
from langchain_community.vectorstores import Chroma
from langchain.prompts.example_selector import SemanticSimilarityExampleSelector
from langchain_experimental.sql import SQLDatabaseChain
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.utilities import SQLDatabase

from backend.few_shots import few_shots

# -------------------- Load Environment Variables --------------------
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# Database configuration
db_host = os.getenv("DB_HOST", "localhost")
db_user = os.getenv("DB_USER", "root")
db_password = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME", "tshirts_db")
db_port = os.getenv("DB_PORT", "3306")

if not api_key:
    raise ValueError("GOOGLE_API_KEY is required but not found in .env file")

if not db_password:
    raise ValueError("DB_PASSWORD is required but not found in .env file")

# -------------------- Load LLM --------------------
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=api_key,
    temperature=0.2,
)

# -------------------- Load MySQL Database --------------------
# URL encode the password to handle special characters
from urllib.parse import quote_plus
encoded_password = quote_plus(db_password)
db_uri = f"mysql+mysqlconnector://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"
db = SQLDatabase.from_uri(db_uri)

# -------------------- Setup Few-Shot Embedding & VectorStore --------------------
embeddings = HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')
to_vectorize = [" ".join(example.values()) for example in few_shots]
vectorstore = Chroma.from_texts(to_vectorize, embeddings, metadatas=few_shots)

example_selector = SemanticSimilarityExampleSelector(
    vectorstore=vectorstore,
    k=2
)

# -------------------- Define Prompt --------------------
example_prompt = PromptTemplate(
    input_variables=["Question", "SQLQuery", "SQLResult", "Answer"],
    template="""
Question: {Question}
SQLQuery: {SQLQuery}
SQLResult: {SQLResult}
Answer: {Answer}
""",
)

mysql_prompt = """You are a helpful t-shirt inventory assistant. Given a question about t-shirt inventory, create a MySQL query to get the data, then provide a natural, conversational answer.

Guidelines:
- Unless specified, query for at most {top_k} results using LIMIT clause
- Only query columns needed to answer the question
- Wrap column names in backticks (`)
- Use CURDATE() for current date questions
- Pay attention to table relationships and column names

Make your answers conversational and helpful:
- Use natural language like "You have X shirts" instead of just "X"
- Include units and context (e.g., "$1,200" instead of "1200")
- For zero results, suggest alternatives or explain what brands/options are available
- Use proper formatting for lists and monetary values

Use the following format:

Question: Question here
SQLQuery: Query to run with no pre-amble
SQLResult: Result of the SQLQuery
Answer: Natural, conversational answer based on the SQLResult

"""

CUSTOM_PROMPT_SUFFIX = """Only use the following tables:
{table_info}

Question: {input}
SQLQuery: """

few_shot_prompt = FewShotPromptTemplate(
    example_selector=example_selector,
    example_prompt=example_prompt,
    prefix=mysql_prompt,
    suffix=CUSTOM_PROMPT_SUFFIX,
    input_variables=["input", "table_info", "top_k"],
)

# -------------------- Function: Query Relevance Filter --------------------
def is_database_related_query(query: str) -> bool:
    # Specific t-shirt related keywords
    tshirt_keywords = [
        'tshirt', 't-shirt', 't shirt', 'shirt', 'inventory', 'stock', 'quantity',
        'price', 'cost', 'revenue', 'discount', 'brand', 'color', 'size',
        'nike', 'adidas', 'levi', 'van huesen', 'red', 'blue', 'black', 'white',
        'xs', 'small', 'medium', 'large', 'extra large',
        'sell', 'selling', 'available', 'clothes', 'clothing', 'apparel'
    ]
    
    # Business/inventory related phrases that need to be combined with t-shirt context
    business_keywords = ['how many', 'total', 'sum', 'count', 'store', 'business']
    
    # Non-t-shirt related keywords that should be rejected
    non_tshirt_keywords = [
        'rainbow', 'weather', 'temperature', 'time', 'date', 'politics', 'news',
        'sports', 'movies', 'music', 'food', 'cooking', 'travel', 'animals',
        'books', 'science', 'math', 'history', 'geography', 'biology', 'chemistry'
    ]
    
    q = query.lower()
    
    # First check if query contains non-t-shirt keywords
    if any(nkw in q for nkw in non_tshirt_keywords):
        return False
    
    # Check if query contains t-shirt specific terms
    has_tshirt_terms = any(kw in q for kw in tshirt_keywords)
    
    # Check if query contains business terms AND mentions something clothing related
    has_business_with_context = (
        any(bkw in q for bkw in business_keywords) and 
        any(tkw in q for tkw in ['shirt', 'tshirt', 't-shirt', 'clothes', 'clothing', 'apparel', 'inventory'])
    )
    
    return has_tshirt_terms or has_business_with_context

# -------------------- Function: Query Completeness Validator --------------------
def is_complete_question(query: str) -> bool:
    """Check if the query is a complete question rather than just keywords"""
    q = query.strip().lower()
    
    # Single word or very short queries (just keywords)
    if len(q.split()) <= 2:
        # Allow only if it contains question words or complete phrases
        question_indicators = [
            'how many', 'how much', 'what is', 'what are', 'which', 
            'where', 'when', 'why', 'who', 'total', 'count', 'list'
        ]
        return any(indicator in q for indicator in question_indicators)
    
    # Check for malformed questions with poor grammar
    malformed_patterns = [
        # Pattern: "how my [something] have" - grammatically incorrect
        r'how\s+my\s+\w+.*\s+have',
        # Pattern: "what my [something] is" - grammatically incorrect  
        r'what\s+my\s+\w+.*\s+is',
        # Pattern: incomplete "how" questions without proper structure
        r'how\s+\w+\s+for\s+\w+.*\s+have$',
        # Pattern: mixed up word order
        r'colors?\s+for\s+\w+.*\s+have$'
    ]
    
    import re
    for pattern in malformed_patterns:
        if re.search(pattern, q):
            return False
    
    # Check for question words or clear intent
    question_words = ['how', 'what', 'which', 'where', 'when', 'why', 'who', 'can', 'do', 'is', 'are']
    has_question_word = any(word in q.split()[:3] for word in question_words)  # Check first 3 words
    
    # Check for imperative phrases (commands)
    imperative_phrases = ['show me', 'tell me', 'give me', 'list', 'find', 'get']
    has_imperative = any(phrase in q for phrase in imperative_phrases)
    
    # Has question mark
    has_question_mark = '?' in q
    
    # Additional grammar check for questions starting with "how"
    if q.startswith('how '):
        # Common correct patterns for "how" questions
        correct_how_patterns = [
            'how many', 'how much', 'how do', 'how can', 'how will',
            'how would', 'how should', 'how is', 'how are'
        ]
        has_correct_how_pattern = any(q.startswith(pattern) for pattern in correct_how_patterns)
        
        # If it starts with "how" but doesn't follow correct patterns, it might be malformed
        if not has_correct_how_pattern and len(q.split()) > 3:
            return False
    
    # Check for malformed questions with grammatical errors
    malformed_patterns = [
        'how my',  # "how my colors" instead of "how many colors"
        'what my',  # "what my" instead of "what are my"
        'which my', # "which my" instead of "which are my"
    ]
    if any(q.startswith(pattern) for pattern in malformed_patterns):
        return False
    
    return has_question_word or has_imperative or has_question_mark or len(q.split()) >= 4

# -------------------- Function: Multi-part Query Detector --------------------
def is_multipart_query(query: str) -> bool:
    """Detect if query contains multiple questions or requests"""
    q = query.lower()
    
    # Strong indicators for multi-part queries
    strong_indicators = [
        'also', 'as well', 'plus', 'additionally', 'furthermore',
        'along with', 'together with', 'what about', 'how about'
    ]
    
    # Check for strong indicators first
    if any(indicator in q for indicator in strong_indicators):
        return True
    
    # For "and", be more careful - only split if it separates clear questions
    if ' and ' in q:
        # Don't split if "and" is used within a single concept like "red and blue"
        color_and_patterns = [
            'red and blue', 'black and white', 'blue and red', 'white and black'
        ]
        if any(pattern in q for pattern in color_and_patterns):
            return False
        
        # Don't split size combinations
        size_and_patterns = [
            's and m', 'm and l', 'l and xl', 'xs and s', 'small and medium',
            'medium and large', 'large and xl'
        ]
        if any(pattern in q for pattern in size_and_patterns):
            return False
        
        # Split if "and" separates distinct question patterns
        parts = q.split(' and ')
        if len(parts) >= 2:
            # Check if both parts could be independent questions
            first_part = parts[0].strip()
            second_part = parts[1].strip()
            
            # Both parts should contain question indicators
            question_indicators = ['how many', 'how much', 'what', 'which', 'where', 'when']
            
            first_has_question = any(indicator in first_part for indicator in question_indicators)
            second_has_question = any(indicator in second_part for indicator in question_indicators)
            
            return first_has_question and second_has_question
    
    return False

# -------------------- Function: Multi-part Query Splitter --------------------
def split_multipart_query(query: str) -> list:
    """Split a multi-part query into individual questions"""
    # Common separators for multi-part queries
    separators = [
        ' and ', ' also ', ' as well', ' plus ', ' additionally ',
        ' furthermore ', ' along with ', ' together with ',
        ' what about ', ' how about '
    ]
    
    parts = [query.lower()]
    
    # Split by each separator
    for separator in separators:
        new_parts = []
        for part in parts:
            if separator in part:
                split_parts = part.split(separator)
                new_parts.extend([p.strip() for p in split_parts if p.strip()])
            else:
                new_parts.append(part)
        parts = new_parts
    
    # Clean up and reconstruct proper questions
    cleaned_parts = []
    for part in parts:
        part = part.strip()
        if part:
            # Add question word if missing
            if not any(part.startswith(qw) for qw in ['how', 'what', 'which', 'where', 'when', 'why', 'who']):
                if 'color' in part or 'colors' in part:
                    part = 'what colors ' + part
                elif 'discount' in part or 'rate' in part:
                    part = 'what is the discount rate'
                elif 'price' in part or 'cost' in part:
                    part = 'what is the price of ' + part
                elif 'many' in part or 'count' in part or 'quantity' in part:
                    part = 'how many ' + part
                else:
                    part = 'what is ' + part
            cleaned_parts.append(part)
    
    return cleaned_parts

# -------------------- Function: Multi-part Query Handler --------------------
def handle_multipart_query(query: str) -> str:
    """Handle queries with multiple parts by breaking them down and answering each"""
    import time
    
    parts = split_multipart_query(query)
    
    if len(parts) <= 1:
        return None  # Not actually multipart
    
    answers = []
    for i, part in enumerate(parts, 1):
        try:
            # Process each part individually
            if is_database_related_query(part):
                chain = SQLDatabaseChain.from_llm(
                    llm=llm,
                    db=db,
                    prompt=few_shot_prompt,
                    return_intermediate_steps=True,
                    verbose=False
                )
                
                result = chain.invoke({"query": part})
                
                # Extract answer
                if 'result' in result:
                    answer = result['result']
                    if "Answer:" in answer:
                        clean_answer = answer.split("Answer:")[-1].strip()
                    elif answer.upper().strip().startswith('SELECT'):
                        sql_result = db.run(answer)
                        clean_answer = str(sql_result).replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace(",", "").replace("'", "").replace("Decimal", "").strip()
                    else:
                        clean_answer = answer
                    
                    # Format specific types of answers better
                    if 'discount rate' in part.lower() or 'discount' in part.lower():
                        if any(char.isdigit() for char in clean_answer):
                            # Try to format discount data better
                            lines = clean_answer.split()
                            if len(lines) > 2:
                                formatted_discounts = []
                                for j in range(0, len(lines), 2):
                                    if j + 1 < len(lines):
                                        formatted_discounts.append(f"T-shirt ID {lines[j]}: {lines[j+1]}% discount")
                                clean_answer = "\n".join(formatted_discounts) if formatted_discounts else clean_answer
                    
                    answers.append(f"**Question {i}:** {part.capitalize()}\n**Answer:** {clean_answer}")
                else:
                    answers.append(f"**Question {i}:** {part.capitalize()}\n**Answer:** Could not process this part")
            else:
                answers.append(f"**Question {i}:** {part.capitalize()}\n**Answer:** This part is not related to our t-shirt inventory")
        except Exception as e:
            answers.append(f"**Question {i}:** {part.capitalize()}\n**Answer:** Error processing: {str(e)}")
        
        # Add small delay between parts to avoid rate limiting
        if i < len(parts):  # Don't delay after the last part
            time.sleep(1)
    
    return "🔍 **Multi-part Query Detected** - Breaking it down:\n\n" + "\n\n".join(answers)

# -------------------- Function: Ask Question --------------------
def ask_question(query: str) -> str:
    try:
        # First check if this is a multi-part query
        if is_multipart_query(query):
            multipart_result = handle_multipart_query(query)
            if multipart_result:
                return multipart_result
        
        # Check if query is related to our database
        if not is_database_related_query(query):
            return """❌ I'm sorry, but I can only answer questions related to our t-shirt inventory, pricing, or discounts.

Example questions:
• How many Nike shirts are in stock?
• What colors are available for Levi's?
• What's the revenue from selling all items with discounts?
• What sizes are available for Adidas shirts?"""
        
        # Then check if the query is complete enough to process
        if not is_complete_question(query):
                    # For malformed queries, provide better examples
                    brand_name = ""
                    if "levi" in query.lower():
                        brand_name = "Levi's"
                    elif "nike" in query.lower():
                        brand_name = "Nike"
                    elif "adidas" in query.lower():
                        brand_name = "Adidas"
                    elif "van huesen" in query.lower():
                        brand_name = "Van Huesen"
                    
                    if brand_name:
                        return f"""❌ Your query "{query}" seems incomplete or has grammatical errors. Please ask a complete question.

Examples of complete questions about {brand_name}:
• How many {brand_name} shirts do we have?
• What colors are available for {brand_name}?
• What is the total price of {brand_name} shirts?
• What sizes are available for {brand_name}?
• How much revenue would we get from selling all {brand_name} shirts?"""
                    else:
                        return f"""❌ Your query "{query}" seems incomplete or has grammatical errors. Please ask a complete question.

Examples of complete questions:
• How many Nike shirts do we have?
• What colors are available for Levi's?
• What is the total price of Adidas shirts?
• What sizes are available for Van Huesen?
• How much revenue would we get from selling all shirts?"""        # Print the user query to console for debugging
        print(f"\n🔍 USER QUERY: {query}")
        
        # Only create and run chain if query is relevant
        chain = SQLDatabaseChain.from_llm(
            llm=llm,
            db=db,
            prompt=few_shot_prompt,
            return_intermediate_steps=True,
            verbose=False
        )

        result = chain.invoke({"query": query})
        
        if 'result' in result:
            answer = result['result']
            
            # If the result contains "Answer:" extract what comes after it
            if "Answer:" in answer:
                # Extract and log the SQL query for debugging
                if "SQLQuery:" in answer:
                    lines = answer.split('\n')
                    for line in lines:
                        if line.strip().startswith('SQLQuery:'):
                            sql_query = line.replace('SQLQuery:', '').strip()
                            print(f"📊 SQL QUERY: {sql_query}")
                            break
                
                clean_answer = answer.split("Answer:")[-1].strip()
                return clean_answer
            
            # If we get only the Question and SQLQuery format, it means the chain didn't complete
            # Let's extract the SQL and run it ourselves, then format the answer
            if "SQLQuery:" in answer and not "SQLResult:" in answer:
                lines = answer.split('\n')
                sql_query = None
                for line in lines:
                    if line.strip().startswith('SQLQuery:'):
                        sql_query = line.replace('SQLQuery:', '').strip()
                        break
                
                if sql_query:
                    # Check if the extracted "SQL query" is actually a natural language response
                    # This happens when the LLM rejects the query but we try to parse it as SQL
                    if not sql_query.upper().strip().startswith('SELECT'):
                        # If it doesn't start with SELECT, it's probably a natural language response
                        # Return the original answer instead of trying to execute it
                        return answer
                    
                    # Print the SQL query to console for debugging
                    print(f"📊 SQL QUERY: {sql_query}")
                    
                    try:
                        # Execute the SQL query
                        sql_result = db.run(sql_query)
                        print(f"📋 SQL RESULT: {sql_result}")
                        
                        # Check for None results (non-existent brands/items) or zero results
                        from decimal import Decimal
                        if (sql_result == [(None,)] or sql_result == [] or str(sql_result) == "[(None,)]" or 
                            sql_result == [(0,)] or sql_result == [(Decimal('0'),)] or sql_result == "" or not sql_result):
                            # Extract brand name from query if possible
                            query_words = query.lower().split()
                            potential_brand = None
                            known_brands = ['nike', 'adidas', 'levi', 'van huesen', 'how', 'many', 'do', 'we', 'have', 'the', 'what', 'are', 'there', 'shirts', 't-shirts']
                            
                            # Look for capitalized words or words that aren't common query words
                            original_words = query.split()
                            for word in original_words:
                                clean_word = word.strip('?.,!').lower()
                                if (clean_word not in known_brands and len(clean_word) > 2 and 
                                    not clean_word.isdigit() and clean_word not in ['and', 'for', 'from', 'with']):
                                    potential_brand = word.strip('?.,!')
                                    break
                            
                            if potential_brand:
                                return f"I couldn't find any t-shirts from the brand '{potential_brand}' in your inventory. We currently carry Nike, Adidas, Levi, and Van Huesen brands."
                            else:
                                return "I couldn't find any matching t-shirts in your inventory."
                        
                        # Format the response naturally based on the query type
                        if "how many" in query.lower():
                            # Extract the numeric result
                            result_str = str(sql_result)
                            # Remove brackets, parentheses, quotes, etc.
                            cleaned = result_str.replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace(",", "").replace("'", "").replace("Decimal", "").strip()
                            
                            # Check if this is a zero result for an unknown brand
                            if cleaned == "0":
                                query_words = query.split()
                                potential_brands = []
                                known_brands = ['nike', 'adidas', 'levi', 'van', 'huesen', 'how', 'many', 'do', 'we', 'have', 'the', 'what', 'are', 'there', 'shirts', 't-shirts', 'is', 'total', 'count']
                                
                                for word in query_words:
                                    clean_word = word.strip('?.,!').lower()
                                    if (clean_word not in known_brands and len(clean_word) > 2 and 
                                        not clean_word.isdigit() and clean_word not in ['and', 'for', 'from', 'with']):
                                        potential_brands.append(word.strip('?.,!'))
                                
                                if potential_brands:
                                    brand_name = ' '.join(potential_brands)
                                    return f"I couldn't find any t-shirts from the brand '{brand_name}' in your inventory. We currently carry Nike, Adidas, Levi, and Van Huesen brands."
                            
                            if "nike" in query.lower():
                                return f"You have a total of {cleaned} Nike t-shirts in stock."
                            elif "levi" in query.lower():
                                return f"You have {cleaned} Levi's t-shirts in your inventory."
                            elif "adidas" in query.lower():
                                return f"You have {cleaned} Adidas t-shirts in stock."
                            elif "van huesen" in query.lower():
                                return f"You have {cleaned} Van Huesen t-shirts in stock."
                            else:
                                return f"The total quantity is {cleaned}."
                        
                        elif "color" in query.lower() or "colors" in query.lower():
                            # Handle color-related queries
                            result_str = str(sql_result)
                            if "(" in result_str and ")" in result_str:
                                # Extract colors from result like [('Red',), ('Blue',), ('Black',), ('White',)]
                                import re
                                colors = re.findall(r"'([^']+)'", result_str)
                                if colors:
                                    # Determine brand for personalized response
                                    brand = ""
                                    if "levi" in query.lower():
                                        brand = "Levi's"
                                    elif "nike" in query.lower():
                                        brand = "Nike"
                                    elif "adidas" in query.lower():
                                        brand = "Adidas"
                                    elif "van huesen" in query.lower():
                                        brand = "Van Huesen"
                                    
                                    if brand:
                                        if len(colors) == 1:
                                            return f"{brand} t-shirts are available in {colors[0]} color."
                                        else:
                                            return f"{brand} t-shirts are available in {len(colors)} colors: {', '.join(colors)}."
                                    else:
                                        if len(colors) == 1:
                                            return f"There is {len(colors)} color available: {colors[0]}."
                                        else:
                                            return f"There are {len(colors)} colors available: {', '.join(colors)}."
                                else:
                                    # Fallback to count if we can't extract color names
                                    if result_str.strip() and result_str.strip() != "[]":
                                        cleaned = result_str.replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace(",", "").replace("'", "").strip()
                                        return f"There are {cleaned} different colors available."
                            return "No color information found."
                        
                        elif "which brand has the most" in query.lower() or "which brand has the highest" in query.lower():
                            # Handle brand comparison queries
                            result_str = str(sql_result)
                            import re
                            # Look for pattern like [('Levi', Decimal('1111'))]
                            if "Decimal" in result_str:
                                brand_match = re.search(r"'([^']+)'.*?Decimal\('(\d+)'\)", result_str)
                                if brand_match:
                                    brand_name = brand_match.group(1)
                                    quantity = brand_match.group(2)
                                    return f"{brand_name} has the most t-shirts in stock with {quantity} units."
                            
                            # Fallback parsing
                            cleaned = result_str.replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace(",", "").replace("'", "").replace("Decimal", "").strip()
                            parts = cleaned.split()
                            if len(parts) >= 2:
                                brand = parts[0]
                                quantity = parts[1]
                                return f"{brand} has the most t-shirts in stock with {quantity} units."
                            
                            return cleaned
                        
                        elif "what brand" in query.lower() or ("which brand" in query.lower() and "most" not in query.lower()):
                            # Format brand list
                            result_str = str(sql_result)
                            # Extract brand names
                            brands = []
                            if result_str.startswith("[") and result_str.endswith("]"):
                                # Parse format like [('Nike',), ('Adidas',), ('Levi',), ('Van Huesen',)]
                                import re
                                brand_matches = re.findall(r"'([^']+)'", result_str)
                                brands = brand_matches
                            
                            if brands:
                                return f"We carry {len(brands)} t-shirt brands: {', '.join(brands)}."
                            else:
                                return "We carry multiple t-shirt brands in our inventory."
                        
                        elif "color" in query.lower():
                            # Format color list
                            result_str = str(sql_result)
                            import re
                            color_matches = re.findall(r"'([^']+)'", result_str)
                            if color_matches:
                                colors = color_matches
                                brand = ""
                                if "nike" in query.lower(): brand = "Nike"
                                elif "adidas" in query.lower(): brand = "Adidas" 
                                elif "levi" in query.lower(): brand = "Levi's"
                                elif "van huesen" in query.lower(): brand = "Van Huesen"
                                
                                if brand:
                                    return f"{brand} t-shirts are available in {', '.join(colors)} colors."
                                else:
                                    return f"T-shirts are available in {', '.join(colors)} colors."
                        
                        else:
                            # Generic formatting
                            cleaned = str(sql_result).replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace(",", "").replace("'", "").replace("Decimal", "").strip()
                            return cleaned
                    
                    except Exception as e:
                        return f"Error executing query: {str(e)}"
            
            # If the result is just a SQL query, execute it directly
            elif answer.upper().strip().startswith('SELECT'):
                print(f"📊 SQL QUERY: {answer}")
                sql_result = db.run(answer)
                print(f"📋 SQL RESULT: {sql_result}")
                # Final fallback: clean the intermediate result and check for None/empty
                cleaned = str(sql_result).replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace(",", "").replace("'", "").replace("Decimal", "")
                if cleaned.strip().lower() == "none" or cleaned.strip() == "":
                    # Extract brand name from query
                    query_words = query.split()
                    potential_brand = None
                    known_brands = ['nike', 'adidas', 'levi', 'van huesen', 'how', 'many', 'do', 'we', 'have', 'the', 'what', 'are', 'there', 'shirts', 't-shirts']
                    
                    for word in query_words:
                        clean_word = word.strip('?.,!').lower()  
                        if (clean_word not in known_brands and len(clean_word) > 2 and 
                            not clean_word.isdigit() and clean_word not in ['and', 'for', 'from', 'with']):
                            potential_brand = word.strip('?.,!')
                            break
                    
                    if potential_brand:
                        return f"I couldn't find any t-shirts from the brand '{potential_brand}' in your inventory. We currently carry Nike, Adidas, Levi, and Van Huesen brands."
                    else:
                        return "I couldn't find any matching t-shirts in your inventory."
                
                return cleaned.strip()
            
            # If we still have raw output that contains Question: and SQLQuery:, try to handle it
            elif "Question:" in answer and "SQLQuery:" in answer:
                # This means we got the format but it wasn't properly processed
                # Return a user-friendly message asking to rephrase
                return "I processed your question but couldn't format the answer properly. Please try rephrasing your question or contact support."
            
            # Final fallback - if the answer looks like raw SQL output, try to clean it
            if answer.startswith('[') and answer.endswith(']') or answer.upper().startswith('SELECT'):
                # This looks like raw SQL result or SQL query, handle it
                if answer.upper().startswith('SELECT'):
                    # This is a raw SQL query being returned, execute it and format properly
                    try:
                        print(f"📊 SQL QUERY: {answer}")
                        sql_result = db.run(answer)
                        print(f"📋 SQL RESULT: {sql_result}")
                        
                        # Format the result properly based on query type
                        result_str = str(sql_result)
                        if "color" in query.lower():
                            import re
                            colors = re.findall(r"'([^']+)'", result_str)
                            if colors:
                                brand = ""
                                if "levi" in query.lower(): brand = "Levi's"
                                elif "nike" in query.lower(): brand = "Nike"
                                elif "adidas" in query.lower(): brand = "Adidas"
                                elif "van huesen" in query.lower(): brand = "Van Huesen"
                                
                                if brand:
                                    return f"{brand} t-shirts are available in {len(colors)} colors: {', '.join(colors)}."
                                else:
                                    return f"Available colors: {', '.join(colors)}."
                            else:
                                cleaned = result_str.replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace(",", "").strip()
                                return f"There are {cleaned} different colors available."
                        else:
                            cleaned = result_str.replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace(",", "").replace("'", "").replace("Decimal", "").strip()
                            if "how many" in query.lower():
                                if "levi" in query.lower():
                                    return f"You have {cleaned} Levi's t-shirts in your inventory."
                                elif "nike" in query.lower():
                                    return f"You have {cleaned} Nike t-shirts in stock."
                                elif "adidas" in query.lower():
                                    return f"You have {cleaned} Adidas t-shirts in stock."
                                else:
                                    return f"The total quantity is {cleaned}."
                            else:
                                return cleaned
                    except Exception as e:
                        return "I had trouble processing your query. Please try rephrasing your question."
                else:
                    # This looks like raw SQL result, clean it up
                    cleaned = answer.replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace(",", "").replace("'", "").replace("Decimal", "").strip()
                    
                    # Try to format it naturally based on what we can infer
                    if cleaned.isdigit():
                        if "how many" in query.lower():
                            if "levi" in query.lower():
                                return f"You have {cleaned} Levi's t-shirts in your inventory."
                            elif "nike" in query.lower():
                                return f"You have {cleaned} Nike t-shirts in stock."
                            elif "adidas" in query.lower():
                                return f"You have {cleaned} Adidas t-shirts in stock."
                            else:
                                return f"The total quantity is {cleaned}."
                        else:
                            return cleaned
                    else:
                        return cleaned
            
            return answer
        
                        # Fallback: try intermediate steps
        steps = result.get("intermediate_steps", [])
        if steps and len(steps) >= 4:
            sql_result = steps[3]  # The SQL result is usually at index 3
            if sql_result:
                # Check for None results or zero results first
                from decimal import Decimal
                if (sql_result == [(None,)] or str(sql_result) == "[(None,)]" or sql_result == [(0,)] or 
                    sql_result == [(Decimal('0'),)] or sql_result == "" or not sql_result):
                    query_words = query.lower().split()
                    potential_brand = None
                    known_brands = ['nike', 'adidas', 'levi', 'van huesen', 'how', 'many', 'do', 'we', 'have', 'the', 'what', 'are', 'there', 'shirts', 't-shirts']
                    
                    # Look for capitalized words or words that aren't common query words
                    original_words = query.split()
                    for word in original_words:
                        clean_word = word.strip('?.,!').lower()
                        if (clean_word not in known_brands and len(clean_word) > 2 and 
                            not clean_word.isdigit() and clean_word not in ['and', 'for', 'from', 'with']):
                            potential_brand = word.strip('?.,!')
                            break
                    
                    if potential_brand:
                        return f"I couldn't find any t-shirts from the brand '{potential_brand}' in your inventory. We currently carry Nike, Adidas, Levi, and Van Huesen brands."
                    else:
                        return "I couldn't find any matching t-shirts in your inventory."
                
                cleaned = str(sql_result).replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace(",", "").replace("'", "").replace("Decimal", "")
                if cleaned.strip().lower() == "none":
                    return "I couldn't find any matching t-shirts in your inventory."
                return cleaned.strip()
        
        return "⚠️ No result returned."

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return f"❌ Error: {str(e)}"