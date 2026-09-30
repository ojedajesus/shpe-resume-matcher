'use client';

import { useMemo } from 'react';
import { type ResumeData } from '@/components/dashboard/resume-component';
import { extractKeywords, calculateMatchStats } from '@/lib/utils/keyword-matcher';
import { JDDisplay } from './jd-display';
import { HighlightedResumeView } from './highlighted-resume-view';
import { CheckCircle, Target } from 'lucide-react';
import { useTranslations } from '@/lib/i18n';
import { compareRequirements } from '@/lib/utils/requirement-evidence';

interface JDComparisonViewProps {
  jobDescription: string;
  resumeData: ResumeData;
}

/**
 * Split view comparing job description with resume.
 * Left: JD (read-only)
 * Right: Resume with matching keywords highlighted
 */
export function JDComparisonView({ jobDescription, resumeData }: JDComparisonViewProps) {
  const { t } = useTranslations();

  // Extract keywords from JD
  const keywords = useMemo(() => extractKeywords(jobDescription), [jobDescription]);

  // Build full resume text for stats calculation
  const evidenceLines = useMemo(() => {
    const parts: string[] = [];

    if (resumeData.summary) parts.push(resumeData.summary);

    resumeData.workExperience?.forEach((exp) => {
      if (exp.title) parts.push(exp.title);
      if (exp.company) parts.push(exp.company);
      exp.description?.forEach((d) => parts.push(d));
    });

    resumeData.education?.forEach((edu) => {
      if (edu.degree) parts.push(edu.degree);
      if (edu.institution) parts.push(edu.institution);
    });

    resumeData.personalProjects?.forEach((proj) => {
      if (proj.name) parts.push(proj.name);
      if (proj.role) parts.push(proj.role);
      proj.description?.forEach((d) => parts.push(d));
    });

    if (resumeData.additional) {
      resumeData.additional.technicalSkills?.forEach((s) => parts.push(s));
      resumeData.additional.languages?.forEach((l) => parts.push(l));
      resumeData.additional.certificationsTraining?.forEach((c) => parts.push(c));
    }

    return parts;
  }, [resumeData]);

  const resumeText = useMemo(() => evidenceLines.join(' '), [evidenceLines]);

  // Calculate match statistics
  const stats = useMemo(() => calculateMatchStats(resumeText, keywords), [resumeText, keywords]);
  const requirements = useMemo(
    () => compareRequirements(jobDescription, evidenceLines),
    [jobDescription, evidenceLines]
  );

  return (
    <div className="h-full flex flex-col">
      {/* Stats Bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-white border-b border-paper-tint">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Target className="w-4 h-4 text-blue-600" />
            <span className="text-sm font-mono">
              {t('builder.jdMatch.stats.keywordsExtracted', { count: keywords.size })}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-green-600" />
            <span className="text-sm font-mono">
              {t('builder.jdMatch.stats.matchesFound', { count: stats.matchCount })}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm font-mono text-ink-soft">
            {t('builder.jdMatch.stats.matchRateLabel')}
          </span>
          <span
            className={`text-lg font-bold ${
              stats.matchPercentage >= 50
                ? 'text-green-600'
                : stats.matchPercentage >= 30
                  ? 'text-yellow-600'
                  : 'text-red-600'
            }`}
          >
            {stats.matchPercentage}%
          </span>
        </div>
      </div>

      <div className="border-b border-paper-tint bg-background p-4">
        <h3 className="font-mono text-sm font-bold uppercase">Grounded requirement review</h3>
        <p className="mt-1 text-xs text-ink-soft">
          Required and preferred qualifications are estimated from the pasted job description.
          Missing evidence is a question—not a claim.
        </p>
        <div className="mt-3 grid max-h-44 gap-2 overflow-auto md:grid-cols-2">
          {requirements.map((item, index) => (
            <div
              key={`${item.requirement}-${index}`}
              className="border border-black bg-white p-2 text-xs"
            >
              <span className="font-mono font-bold uppercase text-blue-700">
                {item.priority} · {item.status}
              </span>
              <p className="mt-1">{item.requirement}</p>
              {item.evidence ? (
                <blockquote className="mt-1 border-l-2 border-blue-700 pl-2">
                  “{item.evidence}”
                </blockquote>
              ) : (
                <p className="mt-1 italic">Ask the member for truthful supporting detail.</p>
              )}
            </div>
          ))}
        </div>
      </div>
      {/* Split View */}
      <div className="flex-1 grid grid-cols-2 min-h-0">
        {/* Left: JD */}
        <div className="border-r border-paper-tint overflow-hidden">
          <JDDisplay content={jobDescription} />
        </div>

        {/* Right: Resume with highlights */}
        <div className="overflow-hidden">
          <HighlightedResumeView resumeData={resumeData} keywords={keywords} />
        </div>
      </div>
    </div>
  );
}
