"""
Lambda optimization script for VaniVerse

Analyzes performance metrics and suggests optimizations.
"""

import boto3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any


class LambdaOptimizer:
    """Analyzes and optimizes Lambda function performance"""
    
    def __init__(self, function_name: str, region: str = 'ap-south-1'):
        self.function_name = function_name
        self.region = region
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        self.logs_client = boto3.client('logs', region_name=region)
    
    def analyze_duration_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Analyze Lambda duration metrics"""
        print("Analyzing duration metrics...")
        
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        response = self.cloudwatch_client.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Duration',
            Dimensions=[{'Name': 'FunctionName', 'Value': self.function_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Average', 'Maximum', 'Minimum'],
            ExtendedStatistics=['p50', 'p90', 'p99']
        )
        
        datapoints = response.get('Datapoints', [])
        
        if not datapoints:
            return {'error': 'No data available'}
        
        # Get latest datapoint
        latest = max(datapoints, key=lambda x: x['Timestamp'])
        
        analysis = {
            'average_ms': latest.get('Average', 0),
            'maximum_ms': latest.get('Maximum', 0),
            'minimum_ms': latest.get('Minimum', 0),
            'p50_ms': latest.get('p50', 0),
            'p90_ms': latest.get('p90', 0),
            'p99_ms': latest.get('p99', 0),
            'target_ms': 6000,
            'meets_target': latest.get('Maximum', 0) < 6000
        }
        
        print(f"  Average: {analysis['average_ms']:.0f}ms")
        print(f"  P50: {analysis['p50_ms']:.0f}ms")
        print(f"  P90: {analysis['p90_ms']:.0f}ms")
        print(f"  P99: {analysis['p99_ms']:.0f}ms")
        print(f"  Maximum: {analysis['maximum_ms']:.0f}ms")
        print(f"  Target (<6000ms): {'✓ MET' if analysis['meets_target'] else '✗ NOT MET'}")
        
        return analysis
    
    def analyze_memory_usage(self) -> Dict[str, Any]:
        """Analyze memory usage patterns"""
        print("Analyzing memory usage...")
        
        # Get current configuration
        config = self.lambda_client.get_function_configuration(
            FunctionName=self.function_name
        )
        
        current_memory = config['MemorySize']
        
        # Query CloudWatch Logs for actual memory usage
        log_group = f'/aws/lambda/{self.function_name}'
        
        try:
            query_id = self.logs_client.start_query(
                logGroupName=log_group,
                startTime=int((datetime.now() - timedelta(hours=24)).timestamp()),
                endTime=int(datetime.now().timestamp()),
                queryString='''
                    fields @maxMemoryUsed, @memorySize
                    | stats max(@maxMemoryUsed) as max_used, avg(@maxMemoryUsed) as avg_used
                '''
            )
            
            # Wait for query to complete
            import time
            time.sleep(5)
            
            results = self.logs_client.get_query_results(queryId=query_id)
            
            if results['results']:
                result = results['results'][0]
                max_used = float(next(r['value'] for r in result if r['field'] == 'max_used'))
                avg_used = float(next(r['value'] for r in result if r['field'] == 'avg_used'))
                
                utilization = (max_used / current_memory) * 100
                
                analysis = {
                    'configured_mb': current_memory,
                    'max_used_mb': max_used,
                    'avg_used_mb': avg_used,
                    'utilization_percent': utilization,
                    'recommendation': self._get_memory_recommendation(utilization, current_memory)
                }
                
                print(f"  Configured: {current_memory}MB")
                print(f"  Max used: {max_used:.0f}MB")
                print(f"  Avg used: {avg_used:.0f}MB")
                print(f"  Utilization: {utilization:.1f}%")
                print(f"  Recommendation: {analysis['recommendation']}")
                
                return analysis
        except Exception as e:
            print(f"  Error analyzing memory: {e}")
            return {'error': str(e)}
    
    def _get_memory_recommendation(self, utilization: float, current: int) -> str:
        """Get memory configuration recommendation"""
        if utilization > 90:
            return f"INCREASE to {current * 2}MB (high utilization)"
        elif utilization < 50:
            return f"DECREASE to {current // 2}MB (low utilization, save costs)"
        else:
            return f"KEEP at {current}MB (optimal)"
    
    def analyze_cold_starts(self) -> Dict[str, Any]:
        """Analyze cold start frequency and duration"""
        print("Analyzing cold starts...")
        
        log_group = f'/aws/lambda/{self.function_name}'
        
        try:
            query_id = self.logs_client.start_query(
                logGroupName=log_group,
                startTime=int((datetime.now() - timedelta(hours=24)).timestamp()),
                endTime=int(datetime.now().timestamp()),
                queryString='''
                    fields @timestamp, @initDuration
                    | filter @type = "REPORT"
                    | stats count(@initDuration) as cold_starts, avg(@initDuration) as avg_init_duration
                '''
            )
            
            import time
            time.sleep(5)
            
            results = self.logs_client.get_query_results(queryId=query_id)
            
            if results['results']:
                result = results['results'][0]
                cold_starts = int(next(r['value'] for r in result if r['field'] == 'cold_starts'))
                avg_init = float(next(r['value'] for r in result if r['field'] == 'avg_init_duration'))
                
                analysis = {
                    'cold_starts_24h': cold_starts,
                    'avg_init_duration_ms': avg_init,
                    'recommendation': self._get_cold_start_recommendation(cold_starts, avg_init)
                }
                
                print(f"  Cold starts (24h): {cold_starts}")
                print(f"  Avg init duration: {avg_init:.0f}ms")
                print(f"  Recommendation: {analysis['recommendation']}")
                
                return analysis
        except Exception as e:
            print(f"  Error analyzing cold starts: {e}")
            return {'error': str(e)}
    
    def _get_cold_start_recommendation(self, count: int, duration: float) -> str:
        """Get cold start optimization recommendation"""
        if count > 100:
            return "Consider provisioned concurrency to reduce cold starts"
        elif duration > 3000:
            return "Optimize initialization code and reduce dependencies"
        else:
            return "Cold start performance is acceptable"
    
    def analyze_error_patterns(self) -> Dict[str, Any]:
        """Analyze error patterns"""
        print("Analyzing error patterns...")
        
        log_group = f'/aws/lambda/{self.function_name}'
        
        try:
            query_id = self.logs_client.start_query(
                logGroupName=log_group,
                startTime=int((datetime.now() - timedelta(hours=24)).timestamp()),
                endTime=int(datetime.now().timestamp()),
                queryString='''
                    fields @timestamp, @message
                    | filter @message like /ERROR/ or @message like /Exception/
                    | stats count() as error_count by @message
                    | sort error_count desc
                    | limit 10
                '''
            )
            
            import time
            time.sleep(5)
            
            results = self.logs_client.get_query_results(queryId=query_id)
            
            error_patterns = []
            for result in results['results']:
                message = next((r['value'] for r in result if r['field'] == '@message'), '')
                count = int(next((r['value'] for r in result if r['field'] == 'error_count'), 0))
                error_patterns.append({'message': message[:100], 'count': count})
            
            analysis = {
                'total_error_types': len(error_patterns),
                'top_errors': error_patterns[:5]
            }
            
            print(f"  Total error types: {len(error_patterns)}")
            for i, error in enumerate(error_patterns[:5], 1):
                print(f"  {i}. {error['message'][:80]}... ({error['count']} occurrences)")
            
            return analysis
        except Exception as e:
            print(f"  Error analyzing errors: {e}")
            return {'error': str(e)}
    
    def suggest_optimizations(self) -> List[str]:
        """Generate optimization suggestions"""
        print("\nGenerating optimization suggestions...")
        
        suggestions = []
        
        # Analyze all metrics
        duration = self.analyze_duration_metrics()
        memory = self.analyze_memory_usage()
        cold_starts = self.analyze_cold_starts()
        errors = self.analyze_error_patterns()
        
        # Duration optimizations
        if not duration.get('meets_target', True):
            suggestions.append({
                'priority': 'HIGH',
                'category': 'Performance',
                'suggestion': 'Voice loop exceeds 6s target. Consider:',
                'actions': [
                    'Optimize parallel API calls',
                    'Reduce Bedrock prompt size',
                    'Cache frequently accessed data',
                    'Use Lambda SnapStart for faster cold starts'
                ]
            })
        
        if duration.get('p99_ms', 0) > duration.get('p50_ms', 0) * 2:
            suggestions.append({
                'priority': 'MEDIUM',
                'category': 'Performance',
                'suggestion': 'High P99 latency variance detected',
                'actions': [
                    'Investigate outlier requests',
                    'Add timeout handling for external APIs',
                    'Implement circuit breakers'
                ]
            })
        
        # Memory optimizations
        if not memory.get('error'):
            if memory.get('utilization_percent', 0) > 90:
                suggestions.append({
                    'priority': 'HIGH',
                    'category': 'Memory',
                    'suggestion': memory['recommendation'],
                    'actions': ['Increase Lambda memory allocation']
                })
            elif memory.get('utilization_percent', 0) < 50:
                suggestions.append({
                    'priority': 'LOW',
                    'category': 'Cost',
                    'suggestion': memory['recommendation'],
                    'actions': ['Decrease Lambda memory to reduce costs']
                })
        
        # Cold start optimizations
        if not cold_starts.get('error'):
            if cold_starts.get('cold_starts_24h', 0) > 100:
                suggestions.append({
                    'priority': 'MEDIUM',
                    'category': 'Performance',
                    'suggestion': 'High cold start frequency',
                    'actions': [
                        'Enable provisioned concurrency',
                        'Reduce package size',
                        'Lazy load dependencies'
                    ]
                })
        
        # Error optimizations
        if not errors.get('error') and errors.get('total_error_types', 0) > 0:
            suggestions.append({
                'priority': 'HIGH',
                'category': 'Reliability',
                'suggestion': f"Found {errors['total_error_types']} error types",
                'actions': [
                    'Review and fix top error patterns',
                    'Add better error handling',
                    'Implement retry logic for transient failures'
                ]
            })
        
        # Print suggestions
        print("\n" + "=" * 80)
        print("OPTIMIZATION SUGGESTIONS")
        print("=" * 80)
        
        for i, suggestion in enumerate(suggestions, 1):
            print(f"\n{i}. [{suggestion['priority']}] {suggestion['category']}")
            print(f"   {suggestion['suggestion']}")
            print("   Actions:")
            for action in suggestion['actions']:
                print(f"   - {action}")
        
        if not suggestions:
            print("\n✓ No critical optimizations needed. System is performing well!")
        
        print("=" * 80)
        
        return suggestions
    
    def generate_optimization_report(self, output_file: str = None):
        """Generate comprehensive optimization report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'function_name': self.function_name,
            'region': self.region,
            'analysis': {
                'duration': self.analyze_duration_metrics(),
                'memory': self.analyze_memory_usage(),
                'cold_starts': self.analyze_cold_starts(),
                'errors': self.analyze_error_patterns()
            },
            'suggestions': self.suggest_optimizations()
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n✓ Optimization report saved to: {output_file}")
        
        return report


def main():
    """Main optimizer function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Optimize VaniVerse Lambda function")
    parser.add_argument(
        '--function',
        default='vaniverse-orchestrator-staging',
        help='Lambda function name'
    )
    parser.add_argument(
        '--region',
        default='ap-south-1',
        help='AWS region'
    )
    parser.add_argument(
        '--output',
        help='Output file for optimization report'
    )
    
    args = parser.parse_args()
    
    # Check AWS credentials
    try:
        boto3.client('sts').get_caller_identity()
    except Exception as e:
        print(f"✗ AWS credentials not configured: {e}")
        return 1
    
    # Run optimizer
    print("=" * 80)
    print("VaniVerse Lambda Optimizer")
    print("=" * 80)
    print(f"Function: {args.function}")
    print(f"Region: {args.region}")
    print("=" * 80)
    print()
    
    optimizer = LambdaOptimizer(args.function, args.region)
    
    output_file = args.output or f'optimization_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    optimizer.generate_optimization_report(output_file)
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
