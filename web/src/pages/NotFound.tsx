import { isRouteErrorResponse, Link, useRouteError } from "react-router";
import { PageIntro } from "../components/Section";

const LINK = "text-paper underline decoration-rule-strong underline-offset-4 hover:decoration-paper";

export function NotFound() {
  return (
    <>
      <PageIntro title="There is no page at this address">The link may be out of date, or the address mistyped.</PageIntro>
      <Link to="/" className={LINK}>
        Go to the overview
      </Link>
    </>
  );
}

/** Shown in place of a page that failed to load or threw while rendering. */
export function PageFailed() {
  const error = useRouteError();
  const reason = isRouteErrorResponse(error) ? `${error.status} ${error.statusText}` : error instanceof Error ? error.message : "No reason was given.";
  return (
    <div role="alert" className="mx-auto max-w-[1320px] px-5 py-14 sm:px-8">
      <PageIntro title="This page could not be shown">{reason}</PageIntro>
      <a href="/" className={LINK}>
        Reload from the overview
      </a>
    </div>
  );
}
