import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "~/lib/utils"

const buttonVariants = cva(
  [
    "group/button relative inline-flex w-fit shrink-0 items-center justify-center overflow-hidden rounded-md text-sm font-medium whitespace-nowrap outline-none select-none",
    "transition-[color,background-color,border-color,box-shadow,opacity]",
    "after:pointer-events-none after:absolute after:inset-0 after:content-[''] after:transition-[background-image,opacity]",
    "disabled:pointer-events-none disabled:bg-[var(--bg-disabled)] disabled:text-[var(--fg-disabled)] disabled:shadow-buttons-neutral disabled:after:hidden",
    "[&_svg]:pointer-events-none [&_svg]:relative [&_svg]:z-[1] [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
    "[&>*]:relative [&>*]:z-[1]",
  ].join(" "),
  {
    variants: {
      variant: {
        default: [
          "bg-[var(--button-inverted)] text-[var(--contrast-fg-primary)] shadow-buttons-inverted after:button-inverted-gradient",
          "hover:bg-[var(--button-inverted-hover)] hover:after:button-inverted-hover-gradient",
          "active:bg-[var(--button-inverted-pressed)] active:after:button-inverted-pressed-gradient",
          "focus-visible:shadow-buttons-inverted-focus",
        ].join(" "),
        outline: [
          "bg-[var(--button-neutral)] text-[var(--fg-base)] shadow-buttons-neutral after:button-neutral-gradient",
          "hover:bg-[var(--button-neutral-hover)] hover:after:button-neutral-hover-gradient",
          "active:bg-[var(--button-neutral-pressed)] active:after:button-neutral-pressed-gradient",
          "focus-visible:shadow-buttons-neutral-focus",
          "aria-expanded:bg-[var(--button-neutral-pressed)]",
        ].join(" "),
        secondary: [
          "bg-[var(--button-neutral)] text-[var(--fg-base)] shadow-buttons-neutral after:button-neutral-gradient",
          "hover:bg-[var(--button-neutral-hover)] hover:after:button-neutral-hover-gradient",
          "active:bg-[var(--button-neutral-pressed)] active:after:button-neutral-pressed-gradient",
          "focus-visible:shadow-buttons-neutral-focus",
          "aria-expanded:bg-[var(--button-neutral-pressed)]",
        ].join(" "),
        ghost: [
          "after:hidden bg-[var(--button-transparent)] text-[var(--fg-base)] shadow-none",
          "hover:bg-[var(--button-transparent-hover)]",
          "active:bg-[var(--button-transparent-pressed)]",
          "focus-visible:bg-[var(--bg-base)] focus-visible:shadow-buttons-neutral-focus",
          "aria-expanded:bg-[var(--button-transparent-hover)]",
          "disabled:!bg-transparent disabled:!shadow-none",
        ].join(" "),
        destructive: [
          "bg-[var(--button-danger)] text-[var(--fg-on-color)] shadow-buttons-danger after:button-danger-gradient",
          "hover:bg-[var(--button-danger-hover)] hover:after:button-danger-hover-gradient",
          "active:bg-[var(--button-danger-pressed)] active:after:button-danger-pressed-gradient",
          "focus-visible:shadow-buttons-danger-focus",
        ].join(" "),
        link: "after:hidden bg-transparent text-[var(--fg-base)] shadow-none underline-offset-4 hover:underline",
      },
      size: {
        default:
          "h-8 gap-1.5 px-3 py-1.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        xs: "h-6 gap-1 rounded-[min(var(--radius-md),10px)] px-2 text-xs in-data-[slot=button-group]:rounded-md has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1.5 px-2 py-1 text-[0.8rem] in-data-[slot=button-group]:rounded-md has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-9 gap-1.5 px-4 py-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        icon: "size-8",
        "icon-xs":
          "size-6 rounded-[min(var(--radius-md),10px)] in-data-[slot=button-group]:rounded-md [&_svg:not([class*='size-'])]:size-3",
        "icon-sm":
          "size-7 rounded-[min(var(--radius-md),12px)] in-data-[slot=button-group]:rounded-md",
        "icon-lg": "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
