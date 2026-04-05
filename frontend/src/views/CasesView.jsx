import React from 'react';
import CasesPanel from '../components/CasesPanel';

export default function CasesView() {
  return (
    <main className="px-6 py-6">
      <CasesPanel onCaseClick={(c) => console.log('Case clicked:', c)} />
    </main>
  );
}
