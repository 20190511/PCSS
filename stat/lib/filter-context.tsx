"use client"

import { createContext, useContext, useState, type ReactNode } from "react"
import { subDays, format } from "date-fns"
import type { DateRange } from "react-day-picker"

interface FilterContextType {
  dateRange: DateRange | undefined
  setDateRange: (range: DateRange | undefined) => void
  logType: string
  setLogType: (type: string) => void
  startDateISO: string | undefined
  endDateISO: string | undefined
}

const FilterContext = createContext<FilterContextType | undefined>(undefined)

export function FilterProvider({ children }: { children: ReactNode }) {
  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: subDays(new Date(), 7),
    to: new Date(),
  })
  const [logType, setLogType] = useState("all")

  const startDateISO = dateRange?.from ? format(dateRange.from, "yyyy-MM-dd") : undefined
  const endDateISO = dateRange?.to ? format(dateRange.to, "yyyy-MM-dd") : undefined

  return (
    <FilterContext.Provider
      value={{
        dateRange,
        setDateRange,
        logType,
        setLogType,
        startDateISO,
        endDateISO,
      }}
    >
      {children}
    </FilterContext.Provider>
  )
}

export function useFilter() {
  const context = useContext(FilterContext)
  if (!context) {
    throw new Error("useFilter must be used within FilterProvider")
  }
  return context
}
