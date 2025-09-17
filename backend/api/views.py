from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from core.main_workflow import process_initial_query, process_query
from core.kqa_workflow import qa_app
from core.ned_workflow import ned_app
from core.pvi_workflow import pvi_app
from core.classifier import classify_task_type
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SmartQueryView(APIView):
    def post(self, request):
        try:
            data = request.data
            query = str(data.get('query', '')).strip()
            query_type = data.get('query_type', None)
            metadata = data.get('metadata', {})
            model_name = data.get('model', '70b')  # Default to 70b model

            logger.info(f"SmartQueryView request: query='{query}', query_type={query_type}, metadata={metadata}, model={model_name}")

            if not query:
                logger.error("Query is missing in SmartQueryView")
                return Response({"error": "Query is required"}, status=status.HTTP_400_BAD_REQUEST)

            # Validate model selection
            from core.llm import AVAILABLE_MODELS
            if model_name not in AVAILABLE_MODELS:
                logger.error(f"Invalid model: {model_name}")
                return Response({
                    "error": f"Invalid model '{model_name}'. Available models: {list(AVAILABLE_MODELS.keys())}"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Step 1: If query_type is not provided, classify and prompt/run KQA
            if not query_type:
                logger.info(f"Classifying query: '{query}'")
                task_type = classify_task_type(query)
                logger.info(f"Query classified as: {task_type}")
                
                if task_type == "NED":
                    logger.info("Prompting for NED metadata")
                    return Response({
                        "prompt": "Please provide contact_id and today's_date for NED workflow.",
                        "query_type": "NED",
                        "error": "",
                        "node_outputs": []
                    }, status=status.HTTP_200_OK)
                elif task_type == "PVI":
                    logger.info("Prompting for PVI case_id")
                    return Response({
                        "prompt": "Please provide case_id for PVI workflow.",
                        "query_type": "PVI",
                        "error": "",
                        "node_outputs": []
                    }, status=status.HTTP_200_OK)
                else:  # KQA
                    logger.info(f"Running KQA workflow immediately with model {model_name}")
                    result = qa_app.invoke({"query_text": query, "model_name": model_name})
                    logger.info(f"KQA workflow completed successfully")
                    return Response({
                        "query_type": "KQA",
                        "result": result,
                        "error": "",
                        "model_used": model_name,
                        "node_outputs": result.get('node_outputs', [])
                    }, status=status.HTTP_200_OK)

            # Step 2: If query_type is provided, run the corresponding workflow
            logger.info(f"Running workflow for query_type: {query_type}")
            
            if query_type == "NED":
                contact_id = str(metadata.get('contact_id', '')).strip()
                today_date = str(metadata.get('today\'s_date', '')).strip()
                if not contact_id or not today_date:
                    logger.error("Missing required metadata for NED workflow")
                    return Response({
                        "error": "contact_id and today's_date are required for NED"
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                logger.info(f"Running NED workflow with contact_id={contact_id}, today_date={today_date}, model={model_name}")
                result = ned_app.invoke({
                    "query_text": query,
                    "contact_id": contact_id,
                    "today_date": today_date,
                    "model_name": model_name
                })
                logger.info("NED workflow completed successfully")
                return Response({
                    "query_type": "NED",
                    "result": result,
                    "error": "",
                    "model_used": model_name,
                    "node_outputs": result.get('node_outputs', [])
                }, status=status.HTTP_200_OK)

            elif query_type == "PVI":
                case_id = str(data.get('case_id', '')).strip()
                if not case_id:
                    logger.error("Missing case_id for PVI workflow")
                    return Response({
                        "error": "case_id is required for PVI"
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                logger.info(f"Running PVI workflow with case_id={case_id}, model={model_name}")
                result = pvi_app.invoke({"case_id": case_id, "model_name": model_name})
                logger.info("PVI workflow completed successfully")
                return Response({
                    "query_type": "PVI",
                    "result": result,
                    "error": "",
                    "model_used": model_name,
                    "node_outputs": result.get('node_outputs', [])
                }, status=status.HTTP_200_OK)

            else:
                logger.error(f"Invalid query_type: {query_type}")
                return Response({
                    "error": "Invalid query_type"
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error in SmartQueryView: {str(e)}")
            return Response({"error": f"Server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class QueryView(APIView):
    def post(self, request):
        try:
            data = request.data
            logger.info(f"Raw request data: {data}")

            # Handle request.data as string or dict
            if isinstance(data, str):
                query_input = data.strip()
                metadata = None
                query_type = None
                model_name = "70b"
            else:
                query_input = str(data.get('query', '')).strip()
                metadata = data.get('metadata', None)
                query_type = data.get('query_type', None)
                model_name = data.get('model', '70b')

                # Validate metadata format
                if metadata and isinstance(metadata, dict):
                    contact_id = str(metadata.get('contact_id', '')).strip()
                    today_date = str(metadata.get('today\'s_date', '')).strip()
                    if contact_id and not re.match(r'^003[a-zA-Z0-9]{15}$', contact_id):
                        logger.error(f"Invalid contact_id format: {contact_id}")
                        return Response(
                            {"error": "Invalid contact_id format. Must be a valid 18-character Salesforce ID (e.g., 003Ws000004Fo3qIAC)"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    if today_date and not re.match(r'^\d{4}-\d{2}-\d{2}$', today_date):
                        logger.error(f"Invalid today's_date format: {today_date}")
                        return Response(
                            {"error": "Invalid today's_date format. Must be YYYY-MM-DD (e.g., 2020-06-15)"},
                            status=status.HTTP_400_BAD_REQUEST
                        )

            logger.info(f"Processed request: query='{query_input}', metadata={metadata}, query_type={query_type}, model={model_name}")

            if not query_input:
                logger.error("Query is missing")
                return Response({"error": "Query is required"}, status=status.HTTP_400_BAD_REQUEST)

            # Validate model selection
            from core.llm import AVAILABLE_MODELS
            if model_name not in AVAILABLE_MODELS:
                logger.error(f"Invalid model: {model_name}")
                return Response({
                    "error": f"Invalid model '{model_name}'. Available models: {list(AVAILABLE_MODELS.keys())}"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Run initial query to classify if query_type is not provided
            if not query_type:
                result = process_initial_query(query_input, metadata=metadata, model_name=model_name)
                logger.info(f"Initial query result: {result}")
                if 'prompt' in result:
                    return Response(
                        {"prompt": result['prompt'], "query_type": result['query_type'], "error": result['error'], "model_used": model_name},
                        status=status.HTTP_200_OK
                    )
                query_type = result['query_type']

            # Process the query
            result = process_query(query_input, metadata=metadata, query_type=query_type, model_name=model_name)
            logger.info(f"Query processing result: {result}")
            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return Response({"error": f"Server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class KQAView(APIView):
    def post(self, request):
        try:
            data = request.data
            query = data.get('query', '') if isinstance(data, dict) else data
            model_name = data.get('model', '70b') if isinstance(data, dict) else '70b'
            logger.info(f"Raw KQA request data: query='{query}', model={model_name}")

            if not query:
                logger.error("Query is missing")
                return Response({"error": "Query is required"}, status=status.HTTP_400_BAD_REQUEST)

            # Validate model selection
            from core.llm import AVAILABLE_MODELS
            if model_name not in AVAILABLE_MODELS:
                logger.error(f"Invalid model: {model_name}")
                return Response({
                    "error": f"Invalid model '{model_name}'. Available models: {list(AVAILABLE_MODELS.keys())}"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Run the KQA workflow
            result = qa_app.invoke({"query_text": query, "model_name": model_name})
            logger.info(f"KQA result: {result}")
            
            return Response({
                "answer": result.get("answer", "No answer found"),
                "error": result.get("error", ""),
                "search_terms": result.get("search_terms", ""),
                "sosl_query": result.get("sosl_query", ""),
                "article_count": result.get("article_count", 0),
                "model_used": model_name,
                "node_outputs": result.get("node_outputs", [])
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error processing KQA query: {str(e)}")
            return Response({"error": f"Server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class NEDView(APIView):
    def post(self, request):
        try:
            data = request.data
            logger.info(f"Raw NED request data: {data}")

            # Extract required fields
            query_text = str(data.get('query', '')).strip()
            metadata = data.get('metadata', {})
            model_name = data.get('model', '70b')
            
            # Validate required metadata
            contact_id = str(metadata.get('contact_id', '')).strip()
            today_date = str(metadata.get('today\'s_date', '')).strip()

            if not query_text:
                logger.error("Query is missing")
                return Response({"error": "Query is required"}, status=status.HTTP_400_BAD_REQUEST)

            # Validate model selection
            from core.llm import AVAILABLE_MODELS
            if model_name not in AVAILABLE_MODELS:
                logger.error(f"Invalid model: {model_name}")
                return Response({
                    "error": f"Invalid model '{model_name}'. Available models: {list(AVAILABLE_MODELS.keys())}"
                }, status=status.HTTP_400_BAD_REQUEST)

            if not contact_id or not re.match(r'^003[a-zA-Z0-9]{15}$', contact_id):
                logger.error(f"Invalid contact_id format: {contact_id}")
                return Response(
                    {"error": "Valid contact_id is required. Must be a valid 18-character Salesforce ID (e.g., 003Ws000004Fo3qIAC)"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not today_date or not re.match(r'^\d{4}-\d{2}-\d{2}$', today_date):
                logger.error(f"Invalid today's_date format: {today_date}")
                return Response(
                    {"error": "Valid today's_date is required. Must be YYYY-MM-DD (e.g., 2020-06-15)"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Run the NED workflow
            result = ned_app.invoke({
                "query_text": query_text,
                "contact_id": contact_id,
                "today_date": today_date,
                "model_name": model_name
            })
            
            logger.info(f"NED result: {result}")
            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error processing NED query: {str(e)}")
            return Response({"error": f"Server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PVIView(APIView):
    def post(self, request):
        try:
            data = request.data
            logger.info(f"Raw PVI request data: {data}")

            # Extract case ID and model from request
            case_id = str(data.get('case_id', '')).strip()
            model_name = data.get('model', '70b')
            
            if not case_id:
                logger.error("Case ID is missing")
                return Response({"error": "Case ID is required"}, status=status.HTTP_400_BAD_REQUEST)

            # Validate model selection
            from core.llm import AVAILABLE_MODELS
            if model_name not in AVAILABLE_MODELS:
                logger.error(f"Invalid model: {model_name}")
                return Response({
                    "error": f"Invalid model '{model_name}'. Available models: {list(AVAILABLE_MODELS.keys())}"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Run the PVI workflow
            result = pvi_app.invoke({
                "case_id": case_id,
                "model_name": model_name
            })
            
            logger.info(f"PVI result: {result}")
            
            # Format the response with the requested fields
            response_data = {
                "case_description": result.get("case_description", ""),
                "case_subject": result.get("case_subject", ""),
                "search_terms": result.get("case_subject_terms", []),
                "knowledge_article_id": result.get("knowledge_article_id", ""),
                "knowledge_article_title": result.get("knowledge_article_title", ""),
                "error": result.get("error", ""),
                "model_used": model_name,
                "node_outputs": result.get("node_outputs", [])
            }
            
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error processing PVI query: {str(e)}")
            return Response({"error": f"Server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)