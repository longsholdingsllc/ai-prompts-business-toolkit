/**
 * Live Lead Qualification Agent – ESM Client
 * Endpoint: https://live-lead-qualifier-agent.vercel.app/api/qualify
 */

const ENDPOINT = 'https://live-lead-qualifier-agent.vercel.app/api/qualify';

/**
 * Qualify a lead against the live AI agent.
 * @param {Object} lead - Lead data
 * @param {string} [lead.name]
 * @param {string} [lead.email]
 * @param {string} [lead.company]
 * @param {string} [lead.title]
 * @param {string} [lead.message]
 * @param {string} [lead.budget]
 * @param {string} [lead.timeline]
 * @returns {Promise<Object>} Qualification result
 */
export async function qualifyLead(lead = {}) {
  try {
    const response = await fetch(ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(lead),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Qualification API error ${response.status}: ${errorText}`);
    }

    const result = await response.json();
    return result;
  } catch (err) {
    console.error('[LeadQualifier] Failed to qualify lead:', err);
    // Return a safe fallback so calling code does not crash
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
