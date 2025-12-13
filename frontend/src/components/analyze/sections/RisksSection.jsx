
import React from "react";
import { CollapsibleCard, RiskItem } from "./ReportWidgets";

const RisksSection = ({
    analysisResult,
    expanded,
    onToggle,
    onOpenGuide,
}) => {
    const { risks } = analysisResult || {};

    if (!risks || risks.length === 0) return null;

    return (
        <CollapsibleCard
            title="잠재적 리스크"
            isExpanded={expanded}
            onToggle={onToggle}
            guideKey="risks"
            onOpenGuide={onOpenGuide}
        >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {risks.map((risk, index) => (
                    <RiskItem key={index} risk={risk} />
                ))}
            </div>
        </CollapsibleCard>
    );
};

export default RisksSection;
