"use client";

import { CalendarIcon, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { format } from "date-fns";
import { ko } from "date-fns/locale";
import { useFilter } from "@/lib/filter-context";

export function DashboardHeader() {
  const { dateRange, setDateRange, logType, setLogType } = useFilter();

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/60">
      <div className="container mx-auto px-4 py-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary">
              <Activity className="w-5 h-5 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-foreground">
                로그 분석
              </h1>
              <p className="text-sm text-muted-foreground">PCSS Access Logs</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Select value={logType} onValueChange={setLogType}>
              <SelectTrigger className="w-[140px] bg-secondary border-border">
                <SelectValue placeholder="로그 타입" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">전체</SelectItem>
                <SelectItem value="homepage">Homepage</SelectItem>
                <SelectItem value="search_start">Search Start</SelectItem>
                <SelectItem value="api_call">API Call</SelectItem>
              </SelectContent>
            </Select>

            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  className="w-[240px] justify-start text-left font-normal bg-secondary border-border"
                >
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {dateRange?.from ? (
                    dateRange.to ? (
                      <>
                        {format(dateRange.from, "MM/dd", { locale: ko })} -{" "}
                        {format(dateRange.to, "MM/dd", { locale: ko })}
                      </>
                    ) : (
                      format(dateRange.from, "PPP", { locale: ko })
                    )
                  ) : (
                    <span>날짜 선택</span>
                  )}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="end">
                <Calendar
                  initialFocus
                  mode="range"
                  defaultMonth={dateRange?.from}
                  selected={dateRange}
                  onSelect={setDateRange}
                  numberOfMonths={2}
                  locale={ko}
                />
              </PopoverContent>
            </Popover>
          </div>
        </div>
      </div>
    </header>
  );
}
