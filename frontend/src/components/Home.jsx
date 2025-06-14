import React, { useState } from 'react';
import axios from 'axios';

function Home() {
  const [mode, setMode] = useState('ned'); // 'ned', 'kqa', or 'pvi'
  const [query, setQuery] = useState('');
  const [metadata, setMetadata] = useState({
    contact_id: '',
    today_date: '',
    case_id: ''
  });
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [showMetadataForm, setShowMetadataForm] = useState(true);

  const handleMetadataSubmit = (e) => {
    e.preventDefault();
    if (mode === 'ned' && metadata.contact_id && metadata.today_date) {
      setShowMetadataForm(false);
    } else if (mode === 'pvi' && metadata.case_id) {
      handleSubmit(e);
    }
  };

  const handleBack = () => {
    setShowMetadataForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if ((mode === 'ned' && (!metadata.contact_id || !metadata.today_date)) ||
        (mode === 'pvi' && !metadata.case_id)) {
      setShowMetadataForm(true);
      return;
    }

    setLoading(true);
    try {
      if (mode === 'ned') {
        const payload = {
          query: query,
          metadata: {
            contact_id: metadata.contact_id,
            "today's_date": metadata.today_date
          }
        };
        const res = await axios.post('http://localhost:8000/ned/', payload);
        
        const newChat = {
          query,
          response: res.data,
          timestamp: new Date().toISOString()
        };
        setChatHistory([...chatHistory, newChat]);
        setQuery('');
      } else if (mode === 'pvi') {
        const res = await axios.post('http://localhost:8000/pvi/', { case_id: metadata.case_id });
        console.log('PVI Response:', res.data); // Debug log
        setResponse(res.data);
        setShowMetadataForm(false);
      } else {
        // KQA mode
        const res = await axios.post('http://localhost:8000/kqa/', { query });
        const newChat = {
          query,
          answer: res.data.answer,
          article_count: res.data.article_count,
          search_terms: res.data.search_terms,
          sosl_query: res.data.sosl_query,
          timestamp: new Date().toISOString()
        };
        setChatHistory([...chatHistory, newChat]);
        setQuery('');
      }
    } catch (error) {
      console.error('Error:', error);
      if (mode === 'pvi') {
        setResponse({ error: error.response?.data?.error || 'Failed to process case' });
        setShowMetadataForm(false);
      } else {
        const errorChat = {
          query: mode === 'pvi' ? `Case ID: ${metadata.case_id}` : query,
          error: 'Failed to process query',
          timestamp: new Date().toISOString()
        };
        setChatHistory([...chatHistory, errorChat]);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <div className="bg-white shadow-md">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-800">Query Processor</h1>
          <div className="flex gap-4">
            <button
              className={`px-4 py-2 rounded-full transition-colors ${
                mode === 'ned' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
              onClick={() => {
                setMode('ned');
                setShowMetadataForm(true);
                setResponse(null);
                setChatHistory([]);
              }}
            >
              NED
            </button>
            <button
              className={`px-4 py-2 rounded-full transition-colors ${
                mode === 'kqa' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
              onClick={() => {
                setMode('kqa');
                setShowMetadataForm(false);
                setResponse(null);
                setChatHistory([]);
              }}
            >
              KQA
            </button>
            <button
              className={`px-4 py-2 rounded-full transition-colors ${
                mode === 'pvi' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
              onClick={() => {
                setMode('pvi');
                setShowMetadataForm(true);
                setResponse(null);
                setChatHistory([]);
              }}
            >
              PVI
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto p-6">
        {(mode === 'ned' || mode === 'pvi') && showMetadataForm ? (
          // Metadata Form
          <div className="max-w-lg mx-auto">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-xl font-semibold mb-6 text-gray-800">Enter Required Information</h2>
              <form onSubmit={handleMetadataSubmit}>
                {mode === 'ned' ? (
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
                        type="date"
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
                  ) : 'Continue'}
                </button>
              </form>
            </div>
          </div>
        ) : (
          <div className="flex gap-6">
            {/* Main Content */}
            <div className="flex-1">
              {mode === 'pvi' ? (
                <div className="bg-white rounded-lg shadow-md p-6">
                  <h2 className="text-xl font-semibold mb-4 text-gray-800">Policy Violation Analysis</h2>
                  {loading ? (
                    <div className="flex justify-center items-center h-32">
                      <svg className="animate-spin h-8 w-8 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                    </div>
                  ) : response?.error ? (
                    <div className="text-red-500 p-4 bg-red-50 rounded-lg">
                      {response.error}
                    </div>
                  ) : (
                    <div className="space-y-6">
                      <div>
                        <h3 className="font-medium text-gray-700 mb-3">Case Information</h3>
                        <div className="space-y-3">
                          <p className="text-sm">
                            <span className="font-medium text-gray-600">Case ID:</span>
                            <span className="ml-2 text-gray-800">{metadata.case_id}</span>
                          </p>
                          <p className="text-sm">
                            <span className="font-medium text-gray-600">Case Description:</span>
                            <span className="ml-2 text-gray-800">{response?.case_description}</span>
                          </p>
                          <p className="text-sm">
                            <span className="font-medium text-gray-600">Case Subject:</span>
                            <span className="ml-2 text-gray-800">{response?.case_subject}</span>
                          </p>
                        </div>
                      </div>
                      <div>
                        <h3 className="font-medium text-gray-700 mb-3">Knowledge Article</h3>
                        <div className="space-y-3">
                          <p className="text-sm">
                            <span className="font-medium text-gray-600">Article ID:</span>
                            <span className="ml-2 text-gray-800">{response?.knowledge_article_id || 'Not found'}</span>
                          </p>
                          <p className="text-sm">
                            <span className="font-medium text-gray-600">Article Title:</span>
                            <span className="ml-2 text-gray-800">{response?.knowledge_article_title || 'Not found'}</span>
                          </p>
                        </div>
                      </div>
                      <div>
                        <h3 className="font-medium text-gray-700 mb-3">Search Terms</h3>
                        <div className="flex flex-wrap gap-2">
                          {response?.search_terms?.map((term, index) => (
                            <span key={index} className="bg-gray-100 px-2 py-1 rounded text-sm">{term}</span>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                // Chat Section for NED and KQA
                <div className="bg-white rounded-lg shadow-md overflow-hidden">
                  <div className="h-[600px] flex flex-col">
                    {/* Chat Header */}
                    <div className="p-4 border-b bg-gray-50 flex items-center">
                      {mode === 'ned' && (
                        <button
                          onClick={handleBack}
                          className="mr-4 p-2 hover:bg-gray-200 rounded-full transition-colors"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-gray-600" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
                          </svg>
                        </button>
                      )}
                      <h2 className="text-lg font-semibold text-gray-800">
                        {mode === 'ned' ? 'Product Matching Chat' : 'Knowledge Base Chat'}
                      </h2>
                    </div>

                    {/* Chat History */}
                    <div className="flex-1 overflow-y-auto p-4 space-y-4">
                      {chatHistory.map((chat, index) => (
                        <div key={index} className="flex flex-col space-y-2">
                          {/* User Message */}
                          <div className="flex justify-end">
                            <div className="bg-blue-500 text-white rounded-lg py-2 px-4 max-w-[80%]">
                              <p>{chat.query}</p>
                            </div>
                          </div>
                          
                          {/* Bot Response */}
                          {mode === 'ned' ? (
                            <div className="flex justify-start">
                              <div className="bg-gray-100 rounded-lg py-2 px-4 max-w-[80%]">
                                <p className="font-semibold">Product: {chat.response?.node_outputs?.[0]?.output?.product_name || 'Not found'}</p>
                                <p className="font-semibold">Product ID: {chat.response?.product_id}</p>
                                {chat.response?.error && (
                                  <p className="text-red-500">Error: {chat.response.error}</p>
                                )}
                              </div>
                            </div>
                          ) : (
                            <div className="flex justify-start">
                              <div className="bg-gray-100 rounded-lg py-2 px-4 max-w-[80%]">
                                {chat.error ? (
                                  <p className="text-red-500">Error: {chat.error}</p>
                                ) : (
                                  <p>{chat.answer}</p>
                                )}
                              </div>
                            </div>
                          )}
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
                          placeholder={mode === 'ned' ? "Describe the product you purchased..." : "Ask a question..."}
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
              )}
            </div>

            {/* Workflow Details */}
            {mode !== 'pvi' && (
              <div className="w-96 bg-white rounded-lg shadow-md p-6">
                <h2 className="text-xl font-semibold mb-4 text-gray-800">Workflow Details</h2>
                {mode === 'ned' && chatHistory.length > 0 && (
                  <div className="space-y-6">
                    <div>
                      <h3 className="font-medium text-gray-700 mb-3">Extracted Information</h3>
                      <div className="space-y-3">
                        <p className="text-sm">
                          <span className="font-medium text-gray-600">Product Name:</span>
                          <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].response?.product_name}</span>
                        </p>
                        <p className="text-sm">
                          <span className="font-medium text-gray-600">Effective Date:</span>
                          <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].response?.effective_date}</span>
                        </p>
                        <p className="text-sm">
                          <span className="font-medium text-gray-600">Number of Items:</span>
                          <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].response?.order_items?.length || 0}</span>
                        </p>
                      </div>
                    </div>
                    <div>
                      <h3 className="font-medium text-gray-700 mb-3">Matching Result</h3>
                      <div className="space-y-3">
                        <p className="text-sm">
                          <span className="font-medium text-gray-600">Product ID:</span>
                          <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].response?.product_id}</span>
                        </p>
                        <p className="text-sm">
                          <span className="font-medium text-gray-600">Match Type:</span>
                          <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].response?.node_outputs?.[0]?.output?.match_type || 'none'}</span>
                        </p>
                        <p className="text-sm">
                          <span className="font-medium text-gray-600">Reason:</span>
                          <span className="ml-2 text-gray-800">{chatHistory[chatHistory.length - 1].response?.node_outputs?.[0]?.output?.reason || 'No match found'}</span>
                        </p>
                      </div>
                    </div>
                  </div>
                )}
                {mode === 'kqa' && chatHistory.length > 0 && (
                  <div className="space-y-6">
                    <div>
                      <h3 className="font-medium text-gray-700 mb-3">Search Terms</h3>
                      <p className="text-sm text-gray-800">{chatHistory[chatHistory.length - 1].search_terms}</p>
                    </div>
                    <div>
                      <h3 className="font-medium text-gray-700 mb-3">SOSL Query</h3>
                      <p className="text-sm break-all text-gray-800">{chatHistory[chatHistory.length - 1].sosl_query}</p>
                    </div>
                    <div>
                      <h3 className="font-medium text-gray-700 mb-3">Articles Found</h3>
                      <p className="text-sm text-gray-800">{chatHistory[chatHistory.length - 1].article_count}</p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default Home;