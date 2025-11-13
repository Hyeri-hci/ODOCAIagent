import React from "react";
import { useNavigate } from "react-router-dom";
import HeroSection from "../components/HeroSection";
import HighlightsSection from "../components/HighlightsSection";
import FeaturesSection from "../components/FeaturesSection";

const HomePage = () => {
  const navigate = useNavigate();

  const handleAnalyzeClick = () => {
    navigate("/analyze");
  };

  return (
    <>
      <HeroSection onAnalyzeClick={handleAnalyzeClick} />
      <HighlightsSection />
      <FeaturesSection onAnalyzeClick={handleAnalyzeClick} />
    </>
  );
};

export default HomePage;

