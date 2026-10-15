import { useState } from 'react';
import { Hero } from '@/components/landing/Hero';
import { ProductShowcase } from '@/components/landing/ProductShowcase';
import { ProblemSection } from '@/components/landing/ProblemSection';
import { SolutionSection } from '@/components/landing/SolutionSection';
import { CapabilityNote } from '@/components/landing/CapabilityNote';
import { ContactSection } from '@/components/landing/ContactSection';
import { NewProjectDialog } from '@/components/landing/NewProjectDialog';
import { Button } from '@/components/ui/button';
import logo from '@/assets/archlens-logo.png';

export function Landing() {
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-[1400px] items-center justify-between px-6 py-6 lg:px-12">
        <img src={logo} alt="ArchLens" className="h-10 w-auto" />
        <Button variant="outline" size="sm" onClick={() => setDialogOpen(true)}>
          New project
        </Button>
      </header>

      <Hero onNewProject={() => setDialogOpen(true)} />
      <ProductShowcase />
      <ProblemSection />
      <SolutionSection />
      <CapabilityNote />
      <ContactSection />

      <NewProjectDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  );
}
