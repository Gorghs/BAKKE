import { CaseShell } from "@/features/cases/components/CaseShell";

export default function CaseLayout({ children }: { children: React.ReactNode }) {
  return <CaseShell>{children}</CaseShell>;
}
