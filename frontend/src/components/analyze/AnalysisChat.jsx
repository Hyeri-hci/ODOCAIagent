import React, { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";
import AnalysisReportSection from "./AnalysisReportSection";

const AnalysisChat = ({ userProfile, analysisResult: initialAnalysisResult }) => {
  const [messages, setMessages] = useState([
    {
      id: "initial",
      role: "assistant",
      content: `${userProfile.repositoryUrl} 저장소에 대한 분석이 완료되었습니다! 아래에서 상세 리포트를 확인하실 수 있습니다.`,
      timestamp: new Date(),
    },
  ]);
  
  const [analysisResult, setAnalysisResult] = useState(initialAnalysisResult);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ 
      behavior: "smooth", 
      block: "nearest",
      inline: "nearest"
    });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // GitHub URL 감지 함수
  const detectGitHubUrl = (message) => {
    // github.com 포함된 전체 URL
    const fullUrlMatch = message.match(/(?:https?:\/\/)?(?:www\.)?github\.com\/([\w-]+\/[\w.-]+)/i);
    if (fullUrlMatch) {
      return fullUrlMatch[0].startsWith('http') ? fullUrlMatch[0] : `https://${fullUrlMatch[0]}`;
    }
    
    // 간단한 owner/repo 형식 (공백 없이)
    const trimmed = message.trim();
    const shortMatch = trimmed.match(/^([\w-]+)\/([\w.-]+)$/);
    if (shortMatch) {
      return `https://github.com/${shortMatch[0]}`;
    }
    
    return null;
  };

  // Mock: 다른 프로젝트 분석 결과 생성
  const generateMockAnalysisForProject = (projectUrl) => {
    const projectName = projectUrl.split('/').slice(-2).join('/');
    
    // Mock 데이터 (실제로는 Backend에서 분석)
    const mockProjects = {
      "microsoft/vscode": {
        score: 92,
        projectSummary: "Visual Studio Code는 TypeScript로 작성된 대규모 오픈소스 코드 에디터입니다. Electron 프레임워크를 기반으로 하며, 확장 가능한 아키텍처와 우수한 개발자 경험을 제공합니다.",
        recommendations: [
          {
            id: "vscode_1",
            title: "확장 프로그램 개발",
            description: "VS Code의 API를 활용하여 새로운 확장 프로그램을 개발할 수 있습니다.",
            difficulty: "medium",
            estimatedTime: "1주",
            impact: "high",
            tags: ["extension", "typescript"],
          },
          {
            id: "vscode_2",
            title: "번역 기여",
            description: "한국어 번역을 개선하여 한국 개발자들의 경험을 향상시킬 수 있습니다.",
            difficulty: "easy",
            estimatedTime: "3-4시간",
            impact: "medium",
            tags: ["i18n", "translation"],
          },
        ],
        risks: [
          {
            id: "vscode_risk_1",
            type: "general",
            severity: "low",
            description: "일부 확장 프로그램 API 문서가 업데이트되지 않았습니다.",
          },
        ],
        technicalDetails: {
          languages: ["TypeScript", "JavaScript"],
          framework: "Electron",
          testCoverage: 85,
          contributors: 1500,
          stars: 150000,
          forks: 25000,
        },
        relatedProjects: [
          {
            name: "atom/atom",
            description: "Electron 기반 해커블 텍스트 에디터",
            score: 78,
            stars: 60000,
            match: 85,
            recommendationReason: "VS Code와 동일하게 Electron 프레임워크를 사용하는 텍스트 에디터입니다. 아키텍처 설계와 플러그인 시스템을 비교 학습하기 좋으며, 커뮤니티 기여 방법을 익히기에 적합합니다.",
          },
          {
            name: "microsoft/TypeScript",
            description: "JavaScript에 정적 타입을 추가한 프로그래밍 언어",
            score: 90,
            stars: 95000,
            match: 80,
            recommendationReason: "VS Code가 TypeScript로 작성되어 있어 TypeScript 언어 자체에 기여하면 에디터 개발에도 도움이 됩니다. 컴파일러와 타입 시스템에 대한 깊은 이해를 얻을 수 있습니다.",
          },
          {
            name: "theia-ide/theia",
            description: "클라우드 및 데스크톱 IDE 플랫폼",
            score: 82,
            stars: 19000,
            match: 78,
            recommendationReason: "VS Code의 오픈소스 대안으로, 비슷한 확장 API를 제공합니다. 클라우드 IDE 개발과 분산 아키텍처에 관심이 있다면 적합한 프로젝트입니다.",
          },
          {
            name: "neovim/neovim",
            description: "Vim 기반 확장 가능한 텍스트 에디터",
            score: 85,
            stars: 75000,
            match: 70,
            recommendationReason: "다른 접근 방식의 에디터 개발을 경험할 수 있습니다. Lua 스크립팅과 플러그인 아키텍처를 통해 에디터 확장성에 대한 폭넓은 시각을 얻을 수 있습니다.",
          },
        ],
      },
      "tensorflow/tensorflow": {
        score: 88,
        projectSummary: "TensorFlow는 Google이 개발한 머신러닝 프레임워크입니다. Python, C++, JavaScript 등 다양한 언어를 지원하며, 대규모 머신러닝 모델 학습에 최적화되어 있습니다.",
        recommendations: [
          {
            id: "tf_1",
            title: "튜토리얼 예제 추가",
            description: "한국어 튜토리얼 예제를 추가하여 한국 개발자들의 접근성을 높일 수 있습니다.",
            difficulty: "easy",
            estimatedTime: "4-5시간",
            impact: "high",
            tags: ["documentation", "tutorial"],
          },
          {
            id: "tf_2",
            title: "모델 최적화",
            description: "모바일 디바이스를 위한 모델 최적화 작업에 기여할 수 있습니다.",
            difficulty: "hard",
            estimatedTime: "2-3주",
            impact: "high",
            tags: ["optimization", "mobile"],
          },
        ],
        risks: [
          {
            id: "tf_risk_1",
            type: "general",
            severity: "medium",
            description: "일부 deprecated API가 아직 코드베이스에 남아있습니다.",
          },
        ],
        technicalDetails: {
          languages: ["Python", "C++", "JavaScript"],
          framework: "TensorFlow",
          testCoverage: 78,
          contributors: 2800,
          stars: 180000,
          forks: 88000,
        },
        relatedProjects: [
          {
            name: "pytorch/pytorch",
            description: "Python 기반 딥러닝 프레임워크",
            score: 90,
            stars: 75000,
            match: 88,
            recommendationReason: "TensorFlow와 함께 가장 인기 있는 딥러닝 프레임워크입니다. 동적 계산 그래프와 Pythonic한 API 설계를 통해 ML 프레임워크의 다양한 접근 방식을 비교 학습할 수 있습니다.",
          },
          {
            name: "keras-team/keras",
            description: "고수준 신경망 API",
            score: 85,
            stars: 60000,
            match: 82,
            recommendationReason: "TensorFlow의 공식 고수준 API로 통합되었습니다. 사용자 친화적인 API 설계와 문서화 작업에 기여하면서 ML 라이브러리 개발을 경험할 수 있습니다.",
          },
          {
            name: "scikit-learn/scikit-learn",
            description: "Python 머신러닝 라이브러리",
            score: 88,
            stars: 57000,
            match: 75,
            recommendationReason: "전통적인 머신러닝 알고리즘에 집중한 라이브러리입니다. TensorFlow보다 진입 장벽이 낮으며, 알고리즘 구현과 최적화에 대한 실전 경험을 쌓기 좋습니다.",
          },
          {
            name: "huggingface/transformers",
            description: "최신 NLP 모델 라이브러리",
            score: 92,
            stars: 120000,
            match: 80,
            recommendationReason: "TensorFlow와 PyTorch를 모두 지원하는 최신 NLP 모델 라이브러리입니다. 최신 AI 모델 활용과 배포에 관심이 있다면 매우 유용하며, 활발한 커뮤니티에서 협업 경험을 쌓을 수 있습니다.",
          },
        ],
      },
    };

    // 프로젝트 이름에서 매칭
    const normalizedName = projectName.toLowerCase();
    for (const [key, value] of Object.entries(mockProjects)) {
      if (normalizedName.includes(key.toLowerCase())) {
        return {
          repositoryUrl: projectUrl,
          analysisId: `analysis_${Date.now()}`,
          timestamp: new Date().toISOString(),
          summary: {
            score: value.score,
            healthStatus: value.score >= 80 ? "excellent" : "good",
            contributionOpportunities: value.recommendations.length,
            estimatedImpact: "high",
          },
          projectSummary: value.projectSummary,
          recommendations: value.recommendations,
          risks: value.risks,
          technicalDetails: value.technicalDetails,
          relatedProjects: value.relatedProjects || [],
        };
      }
    }

    // 기본 Mock 데이터
    return {
      repositoryUrl: projectUrl,
      analysisId: `analysis_${Date.now()}`,
      summary: {
        score: 75,
        healthStatus: "good",
        contributionOpportunities: 5,
        estimatedImpact: "medium",
      },
      projectSummary: `${projectName} 저장소에 대한 분석이 완료되었습니다. 전반적으로 양호한 상태의 프로젝트입니다.`,
      recommendations: [
        {
          id: "generic_1",
          title: "문서화 개선",
          description: "프로젝트 문서를 개선하여 새로운 기여자들의 진입 장벽을 낮출 수 있습니다.",
          difficulty: "easy",
          estimatedTime: "3-4시간",
          impact: "medium",
          tags: ["documentation"],
        },
      ],
      risks: [],
      technicalDetails: {
        languages: ["JavaScript", "TypeScript"],
        framework: "Unknown",
        testCoverage: 65,
        contributors: 50,
        stars: 5000,
        forks: 1000,
      },
      relatedProjects: [
        {
          name: "facebook/react",
          description: "사용자 인터페이스를 구축하기 위한 자바스크립트 라이브러리",
          score: 85,
          stars: 220000,
          match: 75,
          recommendationReason: "React는 가장 인기 있는 JavaScript UI 라이브러리로, 컴포넌트 기반 개발과 상태 관리를 배우기에 최적입니다. 활발한 커뮤니티와 풍부한 문서로 처음 오픈소스 기여를 시작하기 좋습니다.",
        },
        {
          name: "nodejs/node",
          description: "Chrome V8 기반 JavaScript 런타임",
          score: 88,
          stars: 100000,
          match: 72,
          recommendationReason: "JavaScript 백엔드 개발의 기반이 되는 런타임입니다. 저수준 시스템 프로그래밍과 성능 최적화에 관심이 있다면 매우 유익하며, 다양한 난이도의 이슈를 제공합니다.",
        },
        {
          name: "vercel/next.js",
          description: "프로덕션을 위한 React 프레임워크",
          score: 82,
          stars: 120000,
          match: 70,
          recommendationReason: "React 기반 풀스택 프레임워크로 서버사이드 렌더링과 정적 사이트 생성을 지원합니다. 모던 웹 개발 트렌드를 익히고 실전 경험을 쌓기에 적합합니다.",
        },
        {
          name: "microsoft/TypeScript",
          description: "JavaScript에 정적 타입을 추가한 프로그래밍 언어",
          score: 90,
          stars: 95000,
          match: 68,
          recommendationReason: "타입 시스템과 컴파일러 개발을 배울 수 있는 프로젝트입니다. JavaScript 생태계에서 매우 중요한 도구이며, 언어 설계와 구현에 대한 깊은 이해를 얻을 수 있습니다.",
        },
      ],
    };
  };

  // Mock: AI 응답 생성
  const generateAIResponse = (userMessage) => {
    const lowerMessage = userMessage.toLowerCase();
    
    // 간단한 키워드 기반 응답 (실제로는 LLM이 처리)
    if (lowerMessage.includes("보안") || lowerMessage.includes("취약점")) {
      return "현재 저장소에서 2개의 중간 수준 보안 취약점이 발견되었습니다. 주로 의존성 패키지의 오래된 버전에서 발생하고 있으며, `npm update` 또는 `npm audit fix`를 실행하여 해결할 수 있습니다. 특히 lodash와 axios 패키지를 최신 버전으로 업데이트하는 것을 권장드립니다.";
    }
    
    if (lowerMessage.includes("문서") || lowerMessage.includes("readme")) {
      return "README.md 개선은 초급 개발자에게 가장 좋은 첫 기여입니다. 현재 README에는 설치 가이드가 부족하고, 사용 예제가 명확하지 않습니다. 다음 섹션들을 추가하는 것을 추천드립니다:\n\n1. Prerequisites (필수 요구사항)\n2. Installation (설치 방법)\n3. Quick Start (빠른 시작)\n4. API Documentation (API 문서)\n5. Contributing Guidelines (기여 가이드)";
    }
    
    if (lowerMessage.includes("시간") || lowerMessage.includes("기간")) {
      return "추천된 작업들의 예상 소요 시간은 다음과 같습니다:\n\n• 문서화 개선: 2-3시간\n• 보안 취약점 수정: 1시간\n• 타입스크립트 마이그레이션: 1-2주\n\n경험 수준에 따라 시간이 달라질 수 있으며, 초급자의 경우 20-30% 정도 더 소요될 수 있습니다.";
    }
    
    if (lowerMessage.includes("어떻게") || lowerMessage.includes("방법")) {
      return "기여를 시작하는 방법은 다음과 같습니다:\n\n1. 저장소를 Fork 합니다\n2. 로컬에 Clone 합니다\n3. 새로운 브랜치를 생성합니다 (예: `git checkout -b feature/improve-readme`)\n4. 변경사항을 커밋합니다\n5. Fork한 저장소에 Push 합니다\n6. Pull Request를 생성합니다\n\n더 자세한 가이드가 필요하시면 말씀해주세요!";
    }

    if (lowerMessage.includes("typescript") || lowerMessage.includes("타입스크립트")) {
      return "TypeScript 마이그레이션은 중급 이상의 개발자에게 적합한 작업입니다. 점진적으로 진행하는 것을 권장드리며, 다음 순서로 진행하면 좋습니다:\n\n1. tsconfig.json 파일 설정\n2. 유틸리티 함수부터 마이그레이션\n3. 컴포넌트를 하나씩 변환\n4. 타입 정의 파일 추가\n\n이 작업은 프로젝트의 유지보수성을 크게 향상시킬 수 있습니다.";
    }

    if (lowerMessage.includes("다른 프로젝트") || lowerMessage.includes("추천")) {
      return "다른 프로젝트 분석을 원하시나요? 분석하고 싶은 프로젝트의 GitHub URL을 입력해주시면 바로 분석해드리겠습니다!\n\n예시:\n• microsoft/vscode\n• tensorflow/tensorflow\n• vercel/next.js";
    }
    
    // 기본 응답
    return "네, 그 부분에 대해 더 자세히 설명드리겠습니다. 구체적으로 어떤 부분이 궁금하신가요? 예를 들어, '어떻게 시작하나요?', '시간이 얼마나 걸리나요?', '보안 문제는 무엇인가요?' 등을 물어보실 수 있습니다.";
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isAnalyzing) return;

    const userMessageContent = inputValue;
    const userMessage = {
      id: `user_${Date.now()}`,
      role: "user",
      content: userMessageContent,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    
    // GitHub URL 감지
    const detectedUrl = detectGitHubUrl(userMessageContent);
    
    if (detectedUrl) {
      // URL이 감지되면 새로운 프로젝트 분석 시작
      setIsAnalyzing(true);
      setIsTyping(true);
      
      // 분석 중 메시지 표시
      const analyzingMessageId = `analyzing_${Date.now()}`;
      const analyzingMessage = {
        id: analyzingMessageId,
        role: "assistant",
        content: `${detectedUrl} 프로젝트를 분석하고 있습니다... 잠시만 기다려주세요.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, analyzingMessage]);
      
      // Mock: 2초 후 새로운 분석 결과 생성
      setTimeout(() => {
        const newAnalysisResult = generateMockAnalysisForProject(detectedUrl);
        setAnalysisResult(newAnalysisResult);
        
        // 분석 중 메시지를 완료 메시지로 교체
        setMessages((prev) => {
          const filtered = prev.filter(msg => msg.id !== analyzingMessageId);
          return [...filtered, {
            id: `ai_${Date.now()}`,
            role: "assistant",
            content: `${detectedUrl} 저장소에 대한 분석이 완료되었습니다! 오른쪽 리포트에서 상세 정보를 확인하실 수 있습니다.`,
            timestamp: new Date(),
          }];
        });
        
        setIsTyping(false);
        setIsAnalyzing(false);
      }, 2000);
    } else {
      // 일반 질문 처리
      setIsTyping(true);
      
      setTimeout(() => {
        const aiResponse = {
          id: `ai_${Date.now()}`,
          role: "assistant",
          content: generateAIResponse(userMessageContent),
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, aiResponse]);
        setIsTyping(false);
      }, 1500);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-4xl font-black text-gray-900 mb-2">
            분석 결과
          </h1>
          <p className="text-gray-600">
            리포트를 확인하시고, 궁금한 점을 질문해보세요
          </p>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
          {/* 왼쪽: 채팅 영역 */}
          <div className="xl:col-span-2 bg-white rounded-3xl shadow-xl border border-gray-100 flex flex-col h-[calc(100vh-200px)] min-h-[600px]">
            {/* 채팅 메시지 영역 */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}
              
              {isTyping && (
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center flex-shrink-0">
                    <span className="text-white font-bold text-sm">ODOC</span>
                  </div>
                  <div className="bg-gray-100 rounded-2xl rounded-tl-none px-5 py-3">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-100"></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-200"></div>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>

            {/* 입력 영역 */}
            <div className="border-t border-gray-100 p-4">
              {isAnalyzing && (
                <div className="mb-3 text-sm text-blue-600 font-semibold flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                  분석 중입니다...
                </div>
              )}
              <div className="flex gap-3">
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="궁금한 점을 물어보세요... (GitHub URL 입력 시 바로 분석)"
                  disabled={isAnalyzing}
                  className="flex-1 px-5 py-3 border-2 border-gray-200 rounded-2xl focus:border-blue-500 focus:outline-none transition-all disabled:bg-gray-100"
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!inputValue.trim() || isTyping || isAnalyzing}
                  className="bg-gradient-to-r from-blue-600 to-purple-600 text-white p-3 rounded-2xl hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all hover:scale-105"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
              
              {/* 추천 질문 */}
              <div className="mt-3 flex flex-wrap gap-2">
                <SuggestedQuestion
                  text="어떻게 시작하나요?"
                  onClick={() => setInputValue("어떻게 시작하나요?")}
                />
                <SuggestedQuestion
                  text="보안 취약점은?"
                  onClick={() => setInputValue("보안 취약점에 대해 자세히 알려주세요")}
                />
                <SuggestedQuestion
                  text="microsoft/vscode 분석"
                  onClick={() => setInputValue("microsoft/vscode")}
                />
              </div>
            </div>
          </div>

          {/* 오른쪽: 분석 리포트 영역 */}
          <div className="xl:col-span-3 space-y-4">
            <AnalysisReportSection 
              analysisResult={analysisResult} 
              isLoading={isAnalyzing}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

const ChatMessage = ({ message }) => {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "items-start gap-3"}`}>
      {!isUser && (
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center flex-shrink-0">
          <span className="text-white font-bold text-sm">ODOC</span>
        </div>
      )}
      
      <div
        className={`max-w-[80%] rounded-2xl px-5 py-3 ${
          isUser
            ? "bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-tr-none"
            : "bg-gray-100 text-gray-900 rounded-tl-none"
        }`}
      >
        <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
      </div>
    </div>
  );
};

const SuggestedQuestion = ({ text, onClick }) => {
  return (
    <button
      onClick={onClick}
      className="text-sm px-4 py-2 bg-gray-100 text-gray-700 rounded-full hover:bg-gray-200 transition-all"
    >
      {text}
    </button>
  );
};

export default AnalysisChat;

