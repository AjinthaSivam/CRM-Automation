import React, { useState } from 'react';
import axios from 'axios';

function Home() {
  const [query, setQuery] = useState('');
  const [metadata, setMetadata] = useState({
    contact_id: '',
    today_date: '',
    case_id: ''
  });
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [currentQueryType, setCurrentQueryType] = useState(null);
  const [showMetadataForm, setShowMetadataForm] = useState(false);
  const [pendingQuery, setPendingQuery] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    try {
      // First, send the query for classification
      const classificationResponse = await axios.post('http://127.0.0.1:8000/smart-query/', {
        query: query
      });

      const { query_type, prompt, result, error } = classificationResponse.data;

      if (error) {
        throw new Error(error);
      }

      if (query_type === 'KQA') {
        // KQA runs immediately
        const newChat = {
          query,
          response: result,
          query_type: 'KQA',
          timestamp: new Date().toISOString()
        };
        setChatHistory([...chatHistory, newChat]);
        setQuery('');
        setCurrentQueryType(null);
        setShowMetadataForm(false);
      } else {
        // NED or PVI need additional information
        setCurrentQueryType(query_type);
        setPendingQuery(query);
        setShowMetadataForm(true);
        setQuery('');
      }

    } catch (error) {
      console.error('Error:', error);
      const errorChat = {
        query,
        error: error.response?.data?.error || 'Failed to process query',
        timestamp: new Date().toISOString()
      };
      setChatHistory([...chatHistory, errorChat]);
      setQuery('');
    } finally {
      setLoading(false);
    }
  };

  const handleMetadataSubmit = async (e) => {
    e.preventDefault();
    
    // Validate required fields
    if (currentQueryType === 'NED' && (!metadata.contact_id || !metadata.today_date)) {
      return;
    }
    if (currentQueryType === 'PVI' && !metadata.case_id) {
      return;
    }

    setLoading(true);
    try {
      let payload;
      if (currentQueryType === 'NED') {
        payload = {
          query: pendingQuery,
          query_type: 'NED',
          metadata: {
            contact_id: metadata.contact_id,
            "today's_date": metadata.today_date
          }
        };
      } else if (currentQueryType === 'PVI') {
        payload = {
          query: pendingQuery,
          query_type: 'PVI',
          case_id: metadata.case_id
        };
      }

      const response = await axios.post('http://127.0.0.1:8000/smart-query/', payload);
      
      const newChat = {
        query: pendingQuery,
        response: response.data.result,
        query_type: currentQueryType,
        metadata: currentQueryType === 'NED' ? metadata : { case_id: metadata.case_id },
        timestamp: new Date().toISOString()
      };
      
      setChatHistory([...chatHistory, newChat]);
      setCurrentQueryType(null);
      setShowMetadataForm(false);
      setPendingQuery('');
      setMetadata({ contact_id: '', today_date: '', case_id: '' });

    } catch (error) {
      console.error('Error:', error);
      const errorChat = {
        query: pendingQuery,
        error: error.response?.data?.error || 'Failed to process request',
        timestamp: new Date().toISOString()
      };
      setChatHistory([...chatHistory, errorChat]);
      setCurrentQueryType(null);
      setShowMetadataForm(false);
      setPendingQuery('');
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    setShowMetadataForm(false);
    setCurrentQueryType(null);
    setPendingQuery('');
    setMetadata({ contact_id: '', today_date: '', case_id: '' });
  };

  const renderChatMessage = (chat) => {
    if (chat.error) {
      return (
        <div className="flex justify-start">
          <div className="bg-red-100 border border-red-300 rounded-lg py-2 px-4 max-w-[80%]">
            <p className="text-red-700">Error: {chat.error}</p>
          </div>
        </div>
      );
    }

    if (chat.query_type === 'KQA') {
      return (
        <div className="flex justify-start">
          <div className="bg-gray-100 rounded-lg py-2 px-4 max-w-[80%]">
            <p className="font-semibold text-sm text-gray-600 mb-1">KQA Response:</p>
            <p>{chat.response?.answer || 'No answer found'}</p>
            {chat.response?.search_terms && (
              <p className="text-xs text-gray-500 mt-1">Search terms: {chat.response.search_terms}</p>
            )}
          </div>
        </div>
      );
    }

    if (chat.query_type === 'NED') {
      return (
        <div className="flex justify-start">
          <div className="bg-gray-100 rounded-lg py-2 px-4 max-w-[80%]">
            <p className="font-semibold text-sm text-gray-600 mb-1">NED Response:</p>
            <p className="font-semibold">Product: {chat.response?.node_outputs?.[0]?.output?.product_name || 'Not found'}</p>
            <p className="font-semibold">Product ID: {chat.response?.product_id || 'Not found'}</p>
            {chat.response?.error && (
              <p className="text-red-500 text-sm">Error: {chat.response.error}</p>
            )}
          </div>
        </div>
      );
    }

    if (chat.query_type === 'PVI') {
      return (
        <div className="flex justify-start">
          <div className="bg-gray-100 rounded-lg py-2 px-4 max-w-[80%]">
            <p className="font-semibold text-sm text-gray-600 mb-1">PVI Response:</p>
            <p className="font-semibold">Case Description: {chat.response?.case_description || 'Not found'}</p>
            <p className="font-semibold">Case Subject: {chat.response?.case_subject || 'Not found'}</p>
            <p className="font-semibold">Article ID: {chat.response?.knowledge_article_id || 'Not found'}</p>
            <p className="font-semibold">Article Title: {chat.response?.knowledge_article_title || 'Not found'}</p>
            {chat.response?.error && (
              <p className="text-red-500 text-sm">Error: {chat.response.error}</p>
            )}
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <div className="bg-white shadow-md">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-800">Smart Query Processor</h1>
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-600">AI-Powered Classification</span>
            {currentQueryType && (
              <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
                {currentQueryType}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto p-6">
        {showMetadataForm ? (
          // Metadata Form for NED/PVI
          <div className="max-w-lg mx-auto">
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="flex items-center mb-6">
                <button
                  onClick={handleBack}
                  className="mr-4 p-2 hover:bg-gray-200 rounded-full transition-colors"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-gray-600" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
                  </svg>
                </button>
                <h2 className="text-xl font-semibold text-gray-800">
                  {currentQueryType === 'NED' ? 'Product Information Required' : 'Case Information Required'}
                </h2>
              </div>
              
              <div className="mb-4 p-4 bg-blue-50 rounded-lg">
                <p className="text-sm text-blue-800">
                  <strong>Your query:</strong> "{pendingQuery}"
                </p>
                <p className="text-sm text-blue-600 mt-1">
                  {currentQueryType === 'NED' 
                    ? 'Please provide the required information to find your purchased products.'
                    : 'Please provide the case ID to analyze policy compliance.'
                  }
                </p>
              </div>

              <form onSubmit={handleMetadataSubmit}>
                {currentQueryType === 'NED' ? (
                  <>
                    <div className="mb-4">
                      <label className="block text-gray-700 text-sm font-bold mb-2">Contact ID</label>
                      <input
                        type="text"
                        value={metadata.contact_id}
                        onChange={(e) => setMetadata({...metadata, contact_id: e.target.value})}
                        className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        placeholder="e.g., 003Ws000004Fo3qIAC"
                        required
                      />
                    </div>
                    <div className="mb-6">
                      <label className="block text-gray-700 text-sm font-bold mb-2">Today's Date</label>
                      <input
                        type="text"
                        value={metadata.today_date}
                        onChange={(e) => setMetadata({...metadata, today_date: e.target.value})}
                        className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        required
                      />
                    </div>
                  </>
                ) : (
                  <div className="mb-6">
                    <label className="block text-gray-700 text-sm font-bold mb-2">Case ID</label>
                    <input
                      type="text"
                      value={metadata.case_id}
                      onChange={(e) => setMetadata({...metadata, case_id: e.target.value})}
                      className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      placeholder="e.g., 5003000000D8cuIAC"
                      required
                    />
                  </div>
                )}
                <button
                  type="submit"
                  className="w-full bg-blue-500 text-white p-3 rounded-lg hover:bg-blue-600 transition-colors"
                  disabled={loading}
                >
                  {loading ? (
                    <svg className="animate-spin h-5 w-5 mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                  ) : 'Process Query'}
                </button>
              </form>
            </div>
          </div>
        ) : (
          <div className="flex gap-6">
            {/* Main Chat Section */}
            <div className="flex-1">
              <div className="bg-white rounded-lg shadow-md overflow-hidden">
                <div className="h-[600px] flex flex-col">
                  {/* Chat Header */}
                  <div className="p-4 border-b bg-gray-50">
                    <h2 className="text-lg font-semibold text-gray-800">Smart Query Chat</h2>
                    <p className="text-sm text-gray-600">Ask any question and I'll automatically classify and process it</p>
                  </div>

                  {/* Chat History */}
                  <div className="flex-1 overflow-y-auto p-4 space-y-4">
                    {chatHistory.map((chat, index) => (
                      <div key={index} className="flex flex-col space-y-2">
                        {/* User Message */}
                        <div className="flex justify-end">
                          <div className="bg-blue-500 text-white rounded-lg py-2 px-4 max-w-[80%]">
                            <p>{chat.query}</p>
                            {chat.query_type && (
                              <p className="text-xs opacity-75 mt-1">Classified as: {chat.query_type}</p>
                            )}
                          </div>
                        </div>
                        
                        {/* Bot Response */}
                        {renderChatMessage(chat)}
                      </div>
                    ))}
                  </div>
                  
                  {/* Query Input */}
                  <div className="p-4 border-t bg-gray-50">
                    <form onSubmit={handleSubmit} className="flex gap-2">
                      <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        className="flex-1 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        placeholder="Ask any question... (e.g., 'Show me the hiking boots I purchased', 'Did the agent breach policy?', 'How do I reset my password?')"
                        required
                      />
                      <button
                        type="submit"
                        className="bg-blue-500 text-white px-6 py-3 rounded-lg hover:bg-blue-600 transition-colors disabled:bg-blue-300"
                        disabled={loading}
                      >
                        {loading ? (
                          <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                        ) : 'Send'}
                      </button>
                    </form>
                  </div>
                </div>
              </div>
            </div>

            {/* Workflow Details */}
            <div className="w-96 bg-white rounded-lg shadow-md p-6">
              <h2 className="text-xl font-semibold mb-4 text-gray-800">Workflow Details</h2>
              
              {chatHistory.length === 0 ? (
                <div className="text-center text-gray-500 py-8">
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                  <p className="mt-2">Start a conversation to see workflow details</p>
                </div>
              ) : (
                <div className="space-y-6">
                  {chatHistory[chatHistory.length - 1].query_type === 'NED' && (
                    <div>
                      <h3 className="font-medium text-gray-700 mb-3">NED Workflow</h3>
                      
                      {/* Node Outputs */}
                      {chatHistory[chatHistory.length - 1].response?.node_outputs && (
                        <div className="space-y-4">
                          <h4 className="text-sm font-semibold text-gray-600">Agent Outputs:</h4>
                          {chatHistory[chatHistory.length - 1].response.node_outputs.map((node, index) => (
                            <div key={index} className="bg-gray-50 rounded-lg p-3 border">
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-xs font-medium text-blue-600 bg-blue-100 px-2 py-1 rounded">
                                  Node {index + 1}
                                </span>
                                <span className="text-xs text-gray-500">
                                  {node.node_name || `Agent ${index + 1}`}
                                </span>
                              </div>
                              
                              {node.output && (
                                <div className="space-y-2">
                                  {Object.entries(node.output).map(([key, value]) => (
                                    <div key={key} className="text-xs">
                                      <span className="font-medium text-gray-600">{key}:</span>
                                      <span className="ml-1 text-gray-800">
                                        {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              )}
                              
                              {node.error && (
                                <div className="text-xs text-red-600 bg-red-50 p-2 rounded">
                                  Error: {node.error}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                      
                      {/* Final Results */}
                      <div className="mt-4 pt-4 border-t">
                        <h4 className="text-sm font-semibold text-gray-600 mb-2">Final Results:</h4>
                        <div className="space-y-2">
                          <div className="text-sm">
                            <span className="font-medium text-gray-600">Product Name:</span>
                            <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].response?.product_name || 'Not found'}</span>
                          </div>
                          <div className="text-sm">
                            <span className="font-medium text-gray-600">Product ID:</span>
                            <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].response?.product_id || 'Not found'}</span>
                          </div>
                          <div className="text-sm">
                            <span className="font-medium text-gray-600">Match Type:</span>
                            <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].response?.node_outputs?.[0]?.output?.match_type || 'none'}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {chatHistory[chatHistory.length - 1].query_type === 'KQA' && (
                    <div>
                      <h3 className="font-medium text-gray-700 mb-3">KQA Workflow</h3>
                      
                      {/* Node Outputs */}
                      {chatHistory[chatHistory.length - 1].response?.node_outputs && (
                        <div className="space-y-4">
                          <h4 className="text-sm font-semibold text-gray-600">Agent Outputs:</h4>
                          {chatHistory[chatHistory.length - 1].response.node_outputs.map((node, index) => (
                            <div key={index} className="bg-gray-50 rounded-lg p-3 border">
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-xs font-medium text-green-600 bg-green-100 px-2 py-1 rounded">
                                  Node {index + 1}
                                </span>
                                <span className="text-xs text-gray-500">
                                  {node.node_name || `Agent ${index + 1}`}
                                </span>
                              </div>
                              
                              {node.output && (
                                <div className="space-y-2">
                                  {Object.entries(node.output).map(([key, value]) => (
                                    <div key={key} className="text-xs">
                                      <span className="font-medium text-gray-600">{key}:</span>
                                      <span className="ml-1 text-gray-800">
                                        {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              )}
                              
                              {node.error && (
                                <div className="text-xs text-red-600 bg-red-50 p-2 rounded">
                                  Error: {node.error}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                      
                      {/* Final Results */}
                      <div className="mt-4 pt-4 border-t">
                        <h4 className="text-sm font-semibold text-gray-600 mb-2">Final Results:</h4>
                        <div className="space-y-2">
                          <div className="text-sm">
                            <span className="font-medium text-gray-600">Answer:</span>
                            <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].response?.answer || 'Not available'}</span>
                          </div>
                          <div className="text-sm">
                            <span className="font-medium text-gray-600">Search Terms:</span>
                            <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].response?.search_terms || 'Not available'}</span>
                          </div>
                          <div className="text-sm">
                            <span className="font-medium text-gray-600">Articles Found:</span>
                            <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].response?.article_count || 0}</span>
                          </div>
                          {chatHistory[chatHistory.length - 1].response?.sosl_query && (
                            <div className="text-sm">
                              <span className="font-medium text-gray-600">SOSL Query:</span>
                              <div className="mt-1 p-2 bg-gray-100 rounded text-xs break-all">
                                {chatHistory[chatHistory.length - 1].response.sosl_query}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {chatHistory[chatHistory.length - 1].query_type === 'PVI' && (
                    <div>
                      <h3 className="font-medium text-gray-700 mb-3">PVI Workflow</h3>
                      
                      {/* Node Outputs */}
                      {chatHistory[chatHistory.length - 1].response?.node_outputs && (
                        <div className="space-y-4">
                          <h4 className="text-sm font-semibold text-gray-600">Agent Outputs:</h4>
                          {chatHistory[chatHistory.length - 1].response.node_outputs.map((node, index) => (
                            <div key={index} className="bg-gray-50 rounded-lg p-3 border">
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-xs font-medium text-purple-600 bg-purple-100 px-2 py-1 rounded">
                                  Node {index + 1}
                                </span>
                                <span className="text-xs text-gray-500">
                                  {node.node_name || `Agent ${index + 1}`}
                                </span>
                              </div>
                              
                              {node.output && (
                                <div className="space-y-2">
                                  {Object.entries(node.output).map(([key, value]) => (
                                    <div key={key} className="text-xs">
                                      <span className="font-medium text-gray-600">{key}:</span>
                                      <span className="ml-1 text-gray-800">
                                        {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              )}
                              
                              {node.error && (
                                <div className="text-xs text-red-600 bg-red-50 p-2 rounded">
                                  Error: {node.error}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                      
                      {/* Final Results */}
                      <div className="mt-4 pt-4 border-t">
                        <h4 className="text-sm font-semibold text-gray-600 mb-2">Final Results:</h4>
                        <div className="space-y-2">
                          <div className="text-sm">
                            <span className="font-medium text-gray-600">Case ID:</span>
                            <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].metadata?.case_id || 'Not available'}</span>
                          </div>
                          <div className="text-sm">
                            <span className="font-medium text-gray-600">Case Description:</span>
                            <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].response?.case_description || 'Not found'}</span>
                          </div>
                          <div className="text-sm">
                            <span className="font-medium text-gray-600">Case Subject:</span>
                            <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].response?.case_subject || 'Not found'}</span>
                          </div>
                          <div className="text-sm">
                            <span className="font-medium text-gray-600">Article ID:</span>
                            <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].response?.knowledge_article_id || 'Not found'}</span>
                          </div>
                          <div className="text-sm">
                            <span className="font-medium text-gray-600">Article Title:</span>
                            <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].response?.knowledge_article_title || 'Not found'}</span>
                          </div>
                          {chatHistory[chatHistory.length - 1].response?.search_terms && (
                            <div className="text-sm">
                              <span className="font-medium text-gray-600">Search Terms:</span>
                              <div className="mt-1 flex flex-wrap gap-1">
                                {chatHistory[chatHistory.length - 1].response.search_terms.map((term, idx) => (
                                  <span key={idx} className="bg-gray-100 px-2 py-1 rounded text-xs">{term}</span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {/* Raw Response for Debugging */}
                  <div className="mt-6 pt-4 border-t">
                    <details className="text-xs">
                      <summary className="cursor-pointer font-medium text-gray-600 hover:text-gray-800">
                        Raw Response (Debug)
                      </summary>
                      <div className="mt-2 p-3 bg-gray-100 rounded overflow-auto max-h-40">
                        <pre className="text-xs text-gray-700">
                          {JSON.stringify(chatHistory[chatHistory.length - 1].response, null, 2)}
                        </pre>
                      </div>
                    </details>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default Home;