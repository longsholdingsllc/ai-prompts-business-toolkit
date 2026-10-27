// Example: Integrate into a React form (works for Income- and Field-service-AI- frontends)

import { qualifyLead } from '../lead-qualifier.js'; // adjust path

async function handleLeadSubmit(formValues) {
  // 1. Call the live qualifier
  const qualification = await qualifyLead({
    name: formValues.name,
    email: formValues.email,
    company: formValues.company,
    title: formValues.title || formValues.jobTitle,
    message: formValues.message || formValues.notes,
    budget: formValues.budget,
    timeline: formValues.timeline || formValues.urgency,
  });

  // 2. Act on the result
  if (qualification.recommended_action === 'qualify') {
    // High-priority – push to sales / CRM immediately
    console.log('Hot lead:', qualification.summary);
    // await sendToCRM(formValues, qualification);
  } else if (qualification.recommended_action === 'nurture') {
    // Add to nurture sequence
    console.log('Nurture lead:', qualification.summary);
  } else {
    // Low priority
    console.log('Low priority lead');
  }

  return qualification;
}

export { handleLeadSubmit };
