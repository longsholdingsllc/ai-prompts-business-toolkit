// Example: Next.js API route wrapper (for surplus-funds-recovery-os or nextjs-with-supabase)
// Place in app/api/qualify-lead/route.ts or pages/api/qualify-lead.ts

import { NextRequest, NextResponse } from 'next/server';

const ENDPOINT = 'https://live-lead-qualifier-agent.vercel.app/api/qualify';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();

    const response = await fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    const result = await response.json();

    // Optional: persist the scored lead in your Supabase / DB here
    // await supabase.from('leads').insert({ ...body, score: result.score, action: result.recommended_action });

    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: 'Qualification failed', details: String(error) },
      { status: 500 }
    );
  }
}
