// SVGR: `import Logo from './x.svg'` yields a React component;
// `import url from './x.svg?url'` yields the asset URL. See next.config.js.
declare module "*.svg" {
  import type { FC, SVGProps } from "react";
  const ReactComponent: FC<SVGProps<SVGSVGElement> & { title?: string }>;
  export default ReactComponent;
}

declare module "*.svg?url" {
  const src: string;
  export default src;
}
