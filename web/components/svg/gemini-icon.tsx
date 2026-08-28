export function GeminiIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      <defs>
        <linearGradient
          id="gemini-icon-gradient"
          x1="0"
          y1="24"
          x2="24"
          y2="0"
          gradientUnits="userSpaceOnUse"
        >
          <stop
            offset="0"
            stopColor="#4285f4"
          />
          <stop
            offset="0.5"
            stopColor="#9b72cb"
          />
          <stop
            offset="1"
            stopColor="#d96570"
          />
        </linearGradient>
      </defs>
      <path
        fill="url(#gemini-icon-gradient)"
        d="M12 0c0 6.627 5.373 12 12 12-6.627 0-12 5.373-12 12 0-6.627-5.373-12-12-12C6.627 12 12 6.627 12 0Z"
      />
    </svg>
  );
}
