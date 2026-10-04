/**
 * Live Lead Qualification Agent – ESM Client
 * Endpoint: https://live-lead-qualifier-agent.vercel.app/api/qualify
 */

const ENDPOINT = 'https://live-lead-qualifier-agent.vercel.app/api/qualify';

export async function qualifyLead(lead = {}) {
  try {
    const response = await fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(lead),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Qualification API error ${response.status}: ${errorText}`);
    }

    return await response.json();
  } catch (err) {
    console.error('[LeadQualifier] Failed to qualify lead:', err);
    return {
      success: false,
      score: 0,
      recommended_action: 'nurture',
      reason: 'API unavailable – defaulting to nurture',
      summary: 'Lead scoring service temporarily unavailable',
      error: String(err.message || err),
      timestamp: new Date().toISOString(),
      agent: 'Live Lead Qualification Agent v1.0 (fallback)',
    };
  }
}

export default qualifyLead;
