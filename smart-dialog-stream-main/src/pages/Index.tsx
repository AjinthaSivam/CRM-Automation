import React, { useState } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ArrowLeft, MessageSquare, Settings, Brain, GitBranch, CheckCircle, XCircle, Clock, Send, Cpu } from "lucide-react";

interface ChatMessage {
  query: string;
  response?: any;
  error?: string;
  query_type?: string;
  metadata?: any;
  timestamp: string;
}

interface NodeOutput {
  node?: string;
  node_name?: string;
  output?: any;
  error?: string;
}

const Index = () => {
  const [query, setQuery] = useState('');
  const [selectedModel, setSelectedModel] = useState('70b');
  const [metadata, setMetadata] = useState({
    contact_id: '',
    today_date: '',
    case_id: ''
  });
  const [loading, setLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [currentQueryType, setCurrentQueryType] = useState<string | null>(null);
  const [showMetadataForm, setShowMetadataForm] = useState(false);
  const [pendingQuery, setPendingQuery] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    try {
      const classificationResponse = await axios.post('http://127.0.0.1:8000/smart-query/', {
        query: query,
        model: selectedModel
      });

      const { query_type, result, error, model_used } = classificationResponse.data;

      if (error) {
        throw new Error(error);
      }

      if (query_type === 'KQA') {
        const newChat: ChatMessage = {
          query,
          response: { ...result, model_used },
          query_type: 'KQA',
          timestamp: new Date().toISOString()
        };
        setChatHistory([...chatHistory, newChat]);
        setQuery('');
        setCurrentQueryType(null);
        setShowMetadataForm(false);
      } else {
        setCurrentQueryType(query_type);
        setPendingQuery(query);
        setShowMetadataForm(true);
        setQuery('');
      }
    } catch (error: any) {
      console.error('Error:', error);
      const errorChat: ChatMessage = {
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

  const handleMetadataSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (currentQueryType === 'NED' && (!metadata.contact_id || !metadata.today_date)) {
      return;
    }
    if (currentQueryType === 'PVI' && !metadata.case_id) {
      return;
    }

    setLoading(true);
    try {
      let payload: any;
      if (currentQueryType === 'NED') {
        payload = {
          query: pendingQuery,
          query_type: 'NED',
          model: selectedModel,
          metadata: {
            contact_id: metadata.contact_id,
            "today's_date": metadata.today_date
          }
        };
      } else if (currentQueryType === 'PVI') {
        payload = {
          query: pendingQuery,
          query_type: 'PVI',
          model: selectedModel,
          case_id: metadata.case_id
        };
      }

      const response = await axios.post('http://127.0.0.1:8000/smart-query/', payload);
      
      const newChat: ChatMessage = {
        query: pendingQuery,
        response: { ...response.data.result, model_used: response.data.model_used },
        query_type: currentQueryType,
        metadata: currentQueryType === 'NED' ? metadata : { case_id: metadata.case_id },
        timestamp: new Date().toISOString()
      };
      
      setChatHistory([...chatHistory, newChat]);
      setCurrentQueryType(null);
      setShowMetadataForm(false);
      setPendingQuery('');
      setMetadata({ contact_id: '', today_date: '', case_id: '' });
    } catch (error: any) {
      console.error('Error:', error);
      const errorChat: ChatMessage = {
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

  // Enhanced workflow diagram with better parsing
  const WorkflowDiagram = ({ type, latestResponse }: { type: string; latestResponse: any }) => {
    // Debug logging to see what data we're getting
    console.log('WorkflowDiagram - Type:', type);
    console.log('WorkflowDiagram - Latest Response:', latestResponse);
    
    const flows = {
      NED: [
        { step: 'query_parsing', label: 'Query Parsing', description: 'Extract product information' },
        { step: 'account_retrieval', label: 'Account Retrieval', description: 'Fetch user account details' },
        { step: 'orderitem_retrieval', label: 'Order Item Retrieval', description: 'Get purchase history' },
        { step: 'product_matching', label: 'Product Matching', description: 'Match with catalog' }
      ],
      KQA: [
        { step: 'extract_terms', label: 'Term Extraction', description: 'Identify search keywords' },
        { step: 'search_articles', label: 'Article Search', description: 'Query knowledge base' },
        { step: 'extract_answer', label: 'Answer Extraction', description: 'Generate response' }
      ],
      PVI: [
        { step: 'case_retrieval', label: 'Case Retrieval', description: 'Fetch case details' },
        { step: 'knowledge_article_retrieval', label: 'Knowledge Search', description: 'Find relevant policies' }
      ]
    };

    const steps = flows[type as keyof typeof flows] || [];
    
    // More flexible parsing of node outputs
    let nodeOutputs: NodeOutput[] = [];
    if (latestResponse) {
      if (Array.isArray(latestResponse.node_outputs)) {
        nodeOutputs = latestResponse.node_outputs;
      } else if (latestResponse.node_outputs && typeof latestResponse.node_outputs === 'object') {
        // Handle case where node_outputs is an object instead of array
        nodeOutputs = Object.values(latestResponse.node_outputs);
      }
    }
    
    console.log('Parsed node outputs:', nodeOutputs);

    const getNodeOutput = (stepName: string) => {
      // Try multiple matching strategies
      let found = nodeOutputs.find((n) => {
        const nodeName = n.node || n.node_name || '';
        return nodeName === stepName || nodeName.includes(stepName) || stepName.includes(nodeName);
      });
      
      if (!found && nodeOutputs.length > 0) {
        // If no exact match, try to match by index for the workflow steps
        const stepIndex = steps.findIndex(s => s.step === stepName);
        if (stepIndex >= 0 && stepIndex < nodeOutputs.length) {
          found = nodeOutputs[stepIndex];
        }
      }
      
      console.log(`Node output for ${stepName}:`, found);
      return found;
    };

    const getAgentColor = (type: string) => {
      switch (type) {
        case 'NED': return 'agent-ned';
        case 'KQA': return 'agent-kqa';
        case 'PVI': return 'agent-pvi';
        default: return 'primary';
      }
    };

    const formatValue = (key: string, value: any): React.ReactNode => {
      if (value === null || value === undefined) {
        return <span className="text-muted-foreground">N/A</span>;
      }
      
      if (typeof value === 'boolean') {
        return value ? 'Yes' : 'No';
      }
      
      if (Array.isArray(value)) {
        if (value.length === 0) {
          return <span className="text-muted-foreground">Empty array</span>;
        }
        
        // Handle arrays of objects (like order_items, articles)
        if (typeof value[0] === 'object') {
          return (
            <div className="space-y-2 max-h-40 overflow-y-auto">
              {value.slice(0, 5).map((item, idx) => (
                <div key={idx} className="bg-background border rounded p-2 text-xs">
                  {Object.entries(item).map(([k, v]) => (
                    <div key={k} className="flex gap-2 mb-1">
                      <span className="font-medium text-muted-foreground min-w-0 flex-shrink-0">
                        {k}:
                      </span>
                      <span className="text-foreground break-words">
                        {String(v)}
                      </span>
                    </div>
                  ))}
                </div>
              ))}
              {value.length > 5 && (
                <div className="text-xs text-muted-foreground text-center p-1">
                  ... and {value.length - 5} more items
                </div>
              )}
            </div>
          );
        }
        
        // Handle arrays of primitives
        return (
          <div className="space-y-1">
            {value.slice(0, 10).map((item, idx) => (
              <div key={idx} className="text-xs bg-background rounded px-2 py-1 border">
                {String(item)}
              </div>
            ))}
            {value.length > 10 && (
              <div className="text-xs text-muted-foreground">
                ... and {value.length - 10} more items
              </div>
            )}
          </div>
        );
      }
      
      if (typeof value === 'object') {
        return (
          <div className="space-y-1 text-xs">
            {Object.entries(value).map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <span className="font-medium text-muted-foreground">{k}:</span>
                <span className="text-foreground break-words">{String(v)}</span>
              </div>
            ))}
          </div>
        );
      }
      
      return String(value);
    };

    return (
      <div className="space-y-4">
        {steps.map((stepInfo, index) => {
          const nodeData = getNodeOutput(stepInfo.step);
          const hasError = nodeData?.error;
          const hasOutput = nodeData?.output && Object.keys(nodeData.output).length > 0;
          
          return (
            <div key={stepInfo.step} className="relative">
              {/* Connection line */}
              {index < steps.length - 1 && (
                <div className="absolute left-6 top-12 w-0.5 h-8 bg-border z-0"></div>
              )}
              
              <div className="relative z-10 flex items-start gap-4">
                {/* Status indicator */}
                <div className="mt-1 flex-shrink-0">
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center border-2 ${
                    hasError 
                      ? 'border-status-error bg-status-error/10 text-status-error'
                      : hasOutput 
                        ? 'border-status-success bg-status-success/10 text-status-success'
                        : 'border-muted-foreground bg-muted text-muted-foreground'
                  }`}>
                    {hasError ? (
                      <XCircle className="w-5 h-5" />
                    ) : hasOutput ? (
                      <CheckCircle className="w-5 h-5" />
                    ) : (
                      <Clock className="w-5 h-5" />
                    )}
                  </div>
                </div>

                {/* Step content */}
                <div className="flex-1 min-w-0">
                  <Card className="border-2 hover:border-primary/20 transition-all">
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <CardTitle className="text-lg font-semibold text-foreground">
                            {stepInfo.label}
                          </CardTitle>
                          <p className="text-sm text-muted-foreground mt-1">
                            {stepInfo.description}
                          </p>
                        </div>
                        <Badge 
                          variant="outline" 
                          className={`text-${getAgentColor(type)} border-${getAgentColor(type)}/20 bg-${getAgentColor(type)}/5`}
                        >
                          {stepInfo.step}
                        </Badge>
                      </div>
                    </CardHeader>
                    
                    <CardContent>
                      {hasError && (
                        <div className="p-3 rounded-lg bg-status-error/5 border border-status-error/20 mb-3">
                          <p className="text-sm text-status-error font-medium">Error occurred</p>
                          <p className="text-xs text-status-error/80 mt-1">{nodeData.error}</p>
                        </div>
                      )}
                      
                      {hasOutput && (
                        <div className="space-y-3">
                          <h4 className="text-sm font-semibold text-foreground">Output:</h4>
                          <div className="grid gap-2">
                            {Object.entries(nodeData.output).map(([key, value]) => (
                              <div key={key} className="flex flex-col gap-1 p-2 rounded-md bg-muted/30">
                                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                                  {key.replace(/_/g, ' ')}
                                </span>
                                <span className="text-sm text-foreground break-words">
                                  {formatValue(key, value)}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {/* Show nodeData even if output parsing fails */}
                      {!hasOutput && !hasError && nodeData && (
                        <div className="space-y-3">
                          <h4 className="text-sm font-semibold text-foreground">Raw Node Data:</h4>
                          <div className="p-3 rounded-lg bg-muted/20 border border-muted/40">
                            {Object.entries(nodeData).map(([key, value]) => (
                              <div key={key} className="flex flex-col gap-1 mb-2">
                                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                                  {key.replace(/_/g, ' ')}
                                </span>
                                <span className="text-sm text-foreground break-words">
                                  {formatValue(key, value)}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {!hasOutput && !hasError && !nodeData && (
                        <div className="p-3 rounded-lg bg-muted/20 border border-muted/40">
                          <p className="text-sm text-muted-foreground">No output data available</p>
                          {/* Show debug info for troubleshooting */}
                          <details className="mt-2">
                            <summary className="text-xs cursor-pointer text-muted-foreground/60">Debug Info</summary>
                            <div className="mt-1 text-xs text-muted-foreground/60">
                              Step: {stepInfo.step}<br/>
                              Available nodes: {nodeOutputs.map(n => n.node || n.node_name || 'unnamed').join(', ')}
                            </div>
                          </details>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  const renderChatMessage = (chat: ChatMessage) => {
    if (chat.error) {
      return (
        <div className="flex justify-start mb-4">
          <Card className="max-w-[80%] border-status-error/20 bg-status-error/5">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <XCircle className="w-4 h-4 text-status-error" />
                <span className="text-sm font-medium text-status-error">Error</span>
              </div>
              <p className="text-sm text-foreground">{chat.error}</p>
            </CardContent>
          </Card>
        </div>
      );
    }

    const getQueryTypeInfo = (type: string) => {
      switch (type) {
        case 'KQA':
          return { label: 'Knowledge Q&A', color: 'agent-kqa', icon: Brain };
        case 'NED':
          return { label: 'Product Search', color: 'agent-ned', icon: GitBranch };
        case 'PVI':
          return { label: 'Policy Validation', color: 'agent-pvi', icon: Settings };
        default:
          return { label: 'Unknown', color: 'muted-foreground', icon: MessageSquare };
      }
    };

    const typeInfo = getQueryTypeInfo(chat.query_type || '');
    const IconComponent = typeInfo.icon;

    return (
      <div className="flex justify-start mb-4">
        <Card className="max-w-[80%] border-2 hover:border-primary/20 transition-all">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <IconComponent className={`w-4 h-4 text-${typeInfo.color}`} />
                <Badge variant="outline" className={`text-${typeInfo.color} border-${typeInfo.color}/20 bg-${typeInfo.color}/5`}>
                  {typeInfo.label}
                </Badge>
              </div>
              {chat.response?.model_used && (
                <Badge variant="secondary" className="text-xs">
                  <Cpu className="w-3 h-3 mr-1" />
                  {chat.response.model_used}
                </Badge>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {chat.query_type === 'KQA' && chat.response && (
              <div className="space-y-3">
                <div>
                  <h4 className="text-sm font-semibold text-foreground mb-2">Answer:</h4>
                  <p className="text-sm text-foreground">{chat.response.answer || 'No answer found'}</p>
                </div>
                {chat.response.search_terms && (
                  <div>
                    <h4 className="text-sm font-semibold text-muted-foreground mb-2">Search Terms:</h4>
                    <p className="text-xs text-muted-foreground">{chat.response.search_terms}</p>
                  </div>
                )}
              </div>
            )}

            {chat.query_type === 'NED' && chat.response && (
              <div className="space-y-3">
                <div className="grid gap-2">
                  <div className="flex justify-between">
                    <span className="text-sm font-medium text-muted-foreground">Product:</span>
                    <span className="text-sm text-foreground font-medium">
                      {chat.response.node_outputs?.[0]?.output?.product_name || 'Not found'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm font-medium text-muted-foreground">Product ID:</span>
                    <span className="text-sm text-foreground font-mono">
                      {chat.response.product_id || 'Not found'}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {chat.query_type === 'PVI' && chat.response && (
              <div className="space-y-3">
                <div className="grid gap-2">
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">Case Description:</span>
                    <p className="text-sm text-foreground mt-1">{chat.response.case_description || 'Not found'}</p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">Article Title:</span>
                    <p className="text-sm text-foreground mt-1">{chat.response.knowledge_article_id || 'Not found'}</p>
                    <p className="text-sm text-foreground mt-1">{chat.response.knowledge_article_title || 'Not found'}</p>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border/40 bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center">
                <Brain className="w-5 h-5 text-primary-foreground" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-foreground">Smart Query Processor</h1>
                <p className="text-sm text-muted-foreground">AI-Powered Multi-Agent System</p>
              </div>
            </div>
            
            <div className="flex items-center gap-4">
              {/* Model Selection */}
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-muted-foreground" />
                <Select value={selectedModel} onValueChange={setSelectedModel}>
                  <SelectTrigger className="w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="70b">Llama-3.1 70B Model</SelectItem>
                    <SelectItem value="405b">Llama-3.1 405B Model</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              {currentQueryType && (
                <Badge variant="outline" className="px-4 py-2 text-sm">
                  Processing: {currentQueryType}
                </Badge>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-6 py-8">
        {showMetadataForm ? (
          <div className="max-w-2xl mx-auto">
            <Card className="border-2">
              <CardHeader>
                <div className="flex items-center gap-4">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleBack}
                    className="shrink-0"
                  >
                    <ArrowLeft className="w-4 h-4" />
                  </Button>
                  <div>
                    <CardTitle className="text-xl">
                      {currentQueryType === 'NED' ? 'Product Information Required' : 'Case Information Required'}
                    </CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">
                      {currentQueryType === 'NED' 
                        ? 'Provide account details to search your purchased products'
                        : 'Enter case ID to analyze policy compliance'
                      }
                    </p>
                  </div>
                </div>
              </CardHeader>
              
              <CardContent className="space-y-6">
                <div className="p-4 rounded-lg bg-primary/5 border border-primary/20">
                  <p className="text-sm text-foreground font-medium mb-1">Your Query:</p>
                  <p className="text-sm text-muted-foreground">"{pendingQuery}"</p>
                </div>

                <form onSubmit={handleMetadataSubmit} className="space-y-4">
                  {currentQueryType === 'NED' ? (
                    <>
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-foreground">Contact ID</label>
                        <Input
                          value={metadata.contact_id}
                          onChange={(e) => setMetadata({...metadata, contact_id: e.target.value})}
                          placeholder="e.g., 003Ws000004Fo3qIAC"
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-foreground">Today's Date</label>
                        <Input
                          value={metadata.today_date}
                          onChange={(e) => setMetadata({...metadata, today_date: e.target.value})}
                          placeholder="e.g., 2024-01-15"
                          required
                        />
                      </div>
                    </>
                  ) : (
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-foreground">Case ID</label>
                      <Input
                        value={metadata.case_id}
                        onChange={(e) => setMetadata({...metadata, case_id: e.target.value})}
                        placeholder="e.g., 5003000000D8cuIAC"
                        required
                      />
                    </div>
                  )}
                  
                  <Button 
                    type="submit" 
                    className="w-full bg-gradient-primary text-primary-foreground" 
                    disabled={loading}
                  >
                    {loading ? 'Processing...' : 'Process Query'}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
            {/* Chat Section */}
            <div className="xl:col-span-2">
              <Card className="h-[700px] flex flex-col">
                <CardHeader className="border-b border-border/40">
                  <div className="flex items-center gap-3">
                    <MessageSquare className="w-5 h-5 text-primary" />
                    <div>
                      <CardTitle>Chat Interface</CardTitle>
                      <p className="text-sm text-muted-foreground">
                        Ask questions to automatically classify and process through the right agent
                      </p>
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="flex-1 overflow-hidden p-0">
                  <div className="h-full flex flex-col">
                    {/* Messages */}
                    <div className="flex-1 overflow-y-auto p-6 space-y-4">
                      {chatHistory.length === 0 ? (
                        <div className="flex items-center justify-center h-full text-center">
                          <div className="space-y-4">
                            <div className="w-16 h-16 rounded-full bg-gradient-primary/10 flex items-center justify-center mx-auto">
                              <MessageSquare className="w-8 h-8 text-primary" />
                            </div>
                            <div>
                              <h3 className="text-lg font-semibold text-foreground">Start a conversation</h3>
                              <p className="text-sm text-muted-foreground max-w-sm">
                                Try asking about products you've purchased, policy compliance, or general questions
                              </p>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <>
                          {chatHistory.map((chat, index) => (
                            <div key={index}>
                              {/* User message */}
                              <div className="flex justify-end mb-4">
                                <Card className="max-w-[80%] bg-primary text-primary-foreground">
                                  <CardContent className="p-4">
                                    <p className="text-sm">{chat.query}</p>
                                    {chat.query_type && (
                                      <p className="text-xs opacity-75 mt-2">
                                        Classified as: {chat.query_type}
                                      </p>
                                    )}
                                  </CardContent>
                                </Card>
                              </div>
                              
                              {/* Agent response */}
                              {renderChatMessage(chat)}
                            </div>
                          ))}
                        </>
                      )}
                    </div>
                    
                    {/* Input */}
                    <div className="border-t border-border/40 p-4">
                      <form onSubmit={handleSubmit} className="flex gap-3">
                        <Input
                          value={query}
                          onChange={(e) => setQuery(e.target.value)}
                          placeholder="Ask about products, policies, or general questions..."
                          className="flex-1"
                          disabled={loading}
                        />
                        <Button 
                          type="submit" 
                          size="icon"
                          disabled={loading || !query.trim()}
                          className="bg-gradient-primary text-primary-foreground shrink-0"
                        >
                          <Send className="w-4 h-4" />
                        </Button>
                      </form>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Workflow Details */}
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <GitBranch className="w-5 h-5" />
                    Workflow Details
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {chatHistory.length === 0 ? (
                    <div className="text-center py-8">
                      <div className="w-12 h-12 rounded-full bg-muted/20 flex items-center justify-center mx-auto mb-3">
                        <GitBranch className="w-6 h-6 text-muted-foreground" />
                      </div>
                      <p className="text-sm text-muted-foreground">
                        Process a query to see the workflow execution
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      <WorkflowDiagram 
                        type={chatHistory[chatHistory.length - 1].query_type || ''} 
                        latestResponse={chatHistory[chatHistory.length - 1].response} 
                      />
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Debug Panel */}
              {chatHistory.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Debug Information</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <details className="text-xs">
                      <summary className="cursor-pointer font-medium text-muted-foreground hover:text-foreground transition-colors">
                        Raw Response Data
                      </summary>
                      <div className="mt-3 p-3 bg-muted/20 rounded-lg overflow-auto max-h-40">
                        <pre className="text-xs text-muted-foreground whitespace-pre-wrap">
                          {JSON.stringify(chatHistory[chatHistory.length - 1].response, null, 2)}
                        </pre>
                      </div>
                    </details>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default Index;