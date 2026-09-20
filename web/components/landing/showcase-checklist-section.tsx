import { ListChecks } from 'lucide-react';
import { InstagramIcon } from '@/components/svg/instagram-icon';
import { btnSignal } from './shared';
import { ShowcaseCard, ShowcasePanel } from './showcase-panel';

export function ShowcaseChecklistSection() {
  return (
    <section
      aria-labelledby="showcase-checklists"
      className="border-t border-line py-16"
    >
      <ShowcasePanel
        id="showcase-checklists"
        heading="Every video becomes a checklist you can run."
        subheading="The Checklists button"
        vignette={
          <>
            A reel about migrating an AI-built database schema. I hit
            Run Checklists on the job page, and the transcript turned
            into three checks - zero-downtime migrations, a rollback
            plan, a staging mirror - to run against my own project
            before I touched a live table.
          </>
        }
        leftCard={
          <ShowcaseCard
            ariaLabel="The job page, ready to run checklists"
            filename="instagram.com/reel/DbyDJomAkQv"
            status="DONE"
            cornerBadge={
              <InstagramIcon
                aria-hidden="true"
                className="absolute bottom-3 right-3 h-9 w-9 rounded-full border border-line bg-canvas p-1.5 shadow-md"
              />
            }
          >
            <div className="max-h-[280px] overflow-hidden p-4 [-webkit-mask-image:linear-gradient(to_bottom,black_70%,transparent)] [mask-image:linear-gradient(to_bottom,black_70%,transparent)]">
              <h4 className="mb-2 text-sm font-semibold leading-snug text-ink">
                Database Migrations for AI-Generated Schemas
              </h4>
              <p className="mb-4 text-xs leading-relaxed text-body">
                Your AI built your database, but it never planned for
                the day you have to change it completely - add a
                field, rename a column, restructure how two tables
                relate.
              </p>
              <span
                aria-hidden="true"
                className={btnSignal}
              >
                Run Checklists
              </span>
            </div>
          </ShowcaseCard>
        }
        rightCard={
          <ShowcaseCard
            ariaLabel="The checklist Ownix generated from the transcript"
            filename="checklist_db-migrations.md"
            cornerBadge={
              <span
                aria-hidden="true"
                className="absolute bottom-3 right-3 flex h-9 w-9 items-center justify-center rounded-full border border-line bg-canvas shadow-md"
              >
                <ListChecks className="h-5 w-5 text-signal" />
              </span>
            }
          >
            <pre className="max-h-[280px] overflow-hidden whitespace-pre-wrap break-words p-4 font-mono text-xs leading-relaxed text-body [-webkit-mask-image:linear-gradient(to_bottom,black_70%,transparent)] [mask-image:linear-gradient(to_bottom,black_70%,transparent)]">
              <span className="text-muted">
                ## Zero-downtime database migrations
              </span>
              {'\n\n'}
              check whether the current project already has
              {'\n'}
              zero-downtime migration scripts that add new{'\n'}
              structures before removing old ones, copy data,
              {'\n'}
              switch application usage, and drop old structures
              {'\n'}
              only after confirmation, present a report...
              {'\n\n'}
              <span className="text-muted">
                ## Database migration rollback plans
              </span>
              {'\n\n'}
              check whether the current project has a defined
              {'\n'}
              rollback plan or script prepared for every{'\n'}
              migration before it starts, present a report...
            </pre>
          </ShowcaseCard>
        }
        closing={
          <>
            This one became six real GitHub issues in this exact
            codebase - a pre-migration snapshot, a restore script, a
            startup guard, a CI dry-run against a sanitized prod copy.
            Each checklist item is phrased as an instruction, not a
            reminder - paste it into your agent and it audits the
            actual codebase, not just your memory of the video. Ownix
            automated the ask; you still did the checking.
          </>
        }
      />
    </section>
  );
}
